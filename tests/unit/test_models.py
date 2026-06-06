"""Tests for the StripeEvent payload model."""

from __future__ import annotations

import json

import pytest

from stripe_webhook_handler.models import StripeEvent


def test_from_payload_parses_fields() -> None:
    payload = json.dumps(
        {
            "id": "evt_1",
            "type": "checkout.session.completed",
            "data": {"object": {"amount_total": 4200}},
        }
    )
    event = StripeEvent.from_payload(payload)
    assert event.id == "evt_1"
    assert event.type == "checkout.session.completed"
    assert event.object == {"amount_total": 4200}


def test_from_payload_accepts_bytes() -> None:
    event = StripeEvent.from_payload(b'{"id":"evt_2","type":"ping"}')
    assert event.id == "evt_2"
    assert event.object == {}


def test_from_payload_rejects_non_object() -> None:
    with pytest.raises(ValueError, match="must be a JSON object"):
        StripeEvent.from_payload("[1, 2, 3]")


def test_from_payload_requires_id_and_type() -> None:
    with pytest.raises(ValueError, match="'id' and 'type'"):
        StripeEvent.from_payload('{"id": "evt_3"}')
