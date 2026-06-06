"""Tests for the webhook handler: routing, idempotency, and verification."""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from stripe_webhook_handler.errors import SignatureVerificationError
from stripe_webhook_handler.handler import DispatchStatus, WebhookHandler
from stripe_webhook_handler.models import StripeEvent

SECRET = "whsec_handler_test"


def _payload(event_id: str, event_type: str) -> str:
    return json.dumps({"id": event_id, "type": event_type, "data": {"object": {"n": 1}}})


def _header(payload: str, timestamp: int, secret: str = SECRET) -> str:
    signed = f"{timestamp}.{payload}".encode()
    sig = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={sig}"


def test_routes_to_correct_handler() -> None:
    handler = WebhookHandler(SECRET)
    seen: list[str] = []

    @handler.register("checkout.session.completed")
    def _on_checkout(event: StripeEvent) -> None:
        seen.append(event.id)

    @handler.register("invoice.paid")
    def _on_invoice(event: StripeEvent) -> None:
        seen.append("WRONG")

    ts = 2_000_000_000
    payload = _payload("evt_a", "checkout.session.completed")
    status = handler.handle(payload, _header(payload, ts), now=ts)

    assert status is DispatchStatus.PROCESSED
    assert seen == ["evt_a"]


def test_duplicate_event_processed_once() -> None:
    handler = WebhookHandler(SECRET)
    calls: list[str] = []

    handler.on("ping", lambda e: calls.append(e.id))

    ts = 2_000_000_000
    payload = _payload("evt_dup", "ping")
    header = _header(payload, ts)

    assert handler.handle(payload, header, now=ts) is DispatchStatus.PROCESSED
    assert handler.handle(payload, header, now=ts) is DispatchStatus.DUPLICATE
    assert calls == ["evt_dup"]


def test_unknown_event_ignored() -> None:
    handler = WebhookHandler(SECRET)
    ts = 2_000_000_000
    payload = _payload("evt_x", "some.unregistered.type")
    status = handler.handle(payload, _header(payload, ts), now=ts)
    assert status is DispatchStatus.IGNORED


def test_unknown_event_still_marked_as_seen() -> None:
    # Even ignored events should not be re-dispatched if they arrive again.
    handler = WebhookHandler(SECRET)
    ts = 2_000_000_000
    payload = _payload("evt_x", "some.unregistered.type")
    header = _header(payload, ts)
    assert handler.handle(payload, header, now=ts) is DispatchStatus.IGNORED
    assert handler.handle(payload, header, now=ts) is DispatchStatus.DUPLICATE


def test_invalid_signature_raises_before_dispatch() -> None:
    handler = WebhookHandler(SECRET)
    calls: list[str] = []
    handler.on("ping", lambda e: calls.append(e.id))

    ts = 2_000_000_000
    payload = _payload("evt_bad", "ping")
    bad_header = _header(payload, ts, secret="whsec_other")

    with pytest.raises(SignatureVerificationError):
        handler.handle(payload, bad_header, now=ts)
    assert calls == []


def test_dispatch_uses_event_object() -> None:
    handler = WebhookHandler(SECRET)
    captured: list[dict[str, int]] = []
    handler.on("ping", lambda e: captured.append(e.object))

    event = StripeEvent.from_payload(_payload("evt_obj", "ping"))
    assert handler.dispatch(event) is DispatchStatus.PROCESSED
    assert captured == [{"n": 1}]
