"""Tests for the in-memory idempotency store."""

from __future__ import annotations

from stripe_webhook_handler.idempotency import (
    IdempotencyStore,
    InMemoryIdempotencyStore,
)


def test_first_mark_is_new() -> None:
    store = InMemoryIdempotencyStore()
    assert store.mark_if_new("evt_1") is True


def test_duplicate_mark_is_not_new() -> None:
    store = InMemoryIdempotencyStore()
    store.mark_if_new("evt_1")
    assert store.mark_if_new("evt_1") is False


def test_seen_reflects_state() -> None:
    store = InMemoryIdempotencyStore()
    assert store.seen("evt_1") is False
    store.mark("evt_1")
    assert store.seen("evt_1") is True


def test_distinct_ids_tracked_independently() -> None:
    store = InMemoryIdempotencyStore()
    assert store.mark_if_new("evt_1") is True
    assert store.mark_if_new("evt_2") is True
    assert len(store) == 2


def test_satisfies_protocol() -> None:
    store: IdempotencyStore = InMemoryIdempotencyStore()
    assert isinstance(store, IdempotencyStore)
