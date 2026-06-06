"""Webhook event routing with built-in idempotency.

:class:`WebhookHandler` ties the pieces together: register a callback per event
type, then feed it raw request bodies. It verifies the signature, parses the
event, skips duplicates via an :class:`IdempotencyStore`, and dispatches to the
registered handler. Unknown event types are accepted and ignored (Stripe
recommends returning ``200`` so it does not retry).

Part of Stripe Webhook Handler by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

import enum
from collections.abc import Callable

from stripe_webhook_handler.idempotency import IdempotencyStore, InMemoryIdempotencyStore
from stripe_webhook_handler.models import StripeEvent
from stripe_webhook_handler.signature import DEFAULT_TOLERANCE_SECONDS, construct_event

EventHandler = Callable[[StripeEvent], None]
"""A callback invoked with a verified, deduplicated event."""


class DispatchStatus(enum.Enum):
    """Outcome of dispatching a single event."""

    PROCESSED = "processed"
    """The event was new and routed to a registered handler."""

    DUPLICATE = "duplicate"
    """The event id was already processed and was skipped."""

    IGNORED = "ignored"
    """The event was new but had no registered handler for its type."""


class WebhookHandler:
    """Verify, deduplicate, and route Stripe webhook events.

    Args:
        secret: The endpoint signing secret (``whsec_...``).
        store: Idempotency store; defaults to an in-memory one.
        tolerance: Replay tolerance in seconds passed to verification.
    """

    def __init__(
        self,
        secret: str,
        *,
        store: IdempotencyStore | None = None,
        tolerance: int = DEFAULT_TOLERANCE_SECONDS,
    ) -> None:
        self._secret = secret
        self._store: IdempotencyStore = store if store is not None else InMemoryIdempotencyStore()
        self._tolerance = tolerance
        self._handlers: dict[str, EventHandler] = {}

    def on(self, event_type: str, handler: EventHandler) -> None:
        """Register ``handler`` for a Stripe ``event_type``.

        Args:
            event_type: e.g. ``checkout.session.completed``.
            handler: Callback invoked with the parsed :class:`StripeEvent`.
        """
        self._handlers[event_type] = handler

    def register(self, event_type: str) -> Callable[[EventHandler], EventHandler]:
        """Decorator form of :meth:`on`.

        Example:
            >>> handler = WebhookHandler("whsec_x")
            >>> @handler.register("invoice.paid")
            ... def _on_paid(event: StripeEvent) -> None:
            ...     ...
        """

        def decorator(fn: EventHandler) -> EventHandler:
            self.on(event_type, fn)
            return fn

        return decorator

    def handle(
        self,
        payload: str | bytes,
        sig_header: str,
        *,
        now: int | None = None,
    ) -> DispatchStatus:
        """Verify, deduplicate, and dispatch a raw webhook request.

        Args:
            payload: The exact request body bytes/text Stripe delivered.
            sig_header: The ``Stripe-Signature`` header value.
            now: Override the current time (UNIX seconds) — useful for tests.

        Returns:
            The :class:`DispatchStatus` describing what happened.

        Raises:
            SignatureVerificationError: If the signature is invalid or expired.
            ValueError: If the payload is not a valid Stripe event object.
        """
        event = construct_event(
            payload, sig_header, self._secret, tolerance=self._tolerance, now=now
        )
        return self.dispatch(event)

    def dispatch(self, event: StripeEvent) -> DispatchStatus:
        """Deduplicate and route an already-verified event.

        Args:
            event: A parsed (and ideally verified) event.

        Returns:
            The :class:`DispatchStatus` describing what happened.
        """
        if not self._store.mark_if_new(event.id):
            return DispatchStatus.DUPLICATE
        handler = self._handlers.get(event.type)
        if handler is None:
            return DispatchStatus.IGNORED
        handler(event)
        return DispatchStatus.PROCESSED
