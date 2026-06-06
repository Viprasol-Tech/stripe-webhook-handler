"""Idempotency tracking so each Stripe event is processed exactly once.

Stripe may deliver the same event more than once (retries, at-least-once
delivery). Recording each event id the first time it is seen lets the handler
skip duplicates. The :class:`IdempotencyStore` protocol keeps the storage
pluggable — swap the in-memory implementation for Redis or a database in
production — while the core dedupe logic stays identical.

Part of Stripe Webhook Handler by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class IdempotencyStore(Protocol):
    """Pluggable store recording which event ids have been processed."""

    def seen(self, event_id: str) -> bool:
        """Return ``True`` if ``event_id`` has already been recorded."""
        ...

    def mark(self, event_id: str) -> None:
        """Record ``event_id`` as processed."""
        ...

    def mark_if_new(self, event_id: str) -> bool:
        """Atomically record ``event_id`` and report whether it was new.

        Returns:
            ``True`` if this is the first time ``event_id`` is seen (caller
            should process it), ``False`` if it is a duplicate (caller should
            skip it).
        """
        ...


class InMemoryIdempotencyStore:
    """A simple in-memory :class:`IdempotencyStore` backed by a ``set``.

    Suitable for tests, single-process apps, and demos. Not shared across
    processes — use a Redis/SQL implementation for multi-worker deployments.
    """

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def seen(self, event_id: str) -> bool:
        """Return ``True`` if ``event_id`` has already been recorded."""
        return event_id in self._seen

    def mark(self, event_id: str) -> None:
        """Record ``event_id`` as processed."""
        self._seen.add(event_id)

    def mark_if_new(self, event_id: str) -> bool:
        """Record ``event_id`` and return whether it was newly added."""
        if event_id in self._seen:
            return False
        self._seen.add(event_id)
        return True

    def __len__(self) -> int:
        """Return how many distinct event ids have been recorded."""
        return len(self._seen)
