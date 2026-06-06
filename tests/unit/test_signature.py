"""Tests for Stripe signature verification against in-test computed HMACs."""

from __future__ import annotations

import hashlib
import hmac

import pytest

from stripe_webhook_handler.errors import SignatureVerificationError
from stripe_webhook_handler.signature import (
    compute_signature,
    construct_event,
    verify_signature,
)

SECRET = "whsec_test_secret"
PAYLOAD = '{"id":"evt_1","type":"checkout.session.completed","data":{"object":{}}}'


def _expected(timestamp: int, payload: str, secret: str) -> str:
    """Independently recompute the HMAC the way Stripe documents it."""
    signed = f"{timestamp}.{payload}".encode()
    return hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()


def _header(timestamp: int, payload: str = PAYLOAD, secret: str = SECRET) -> str:
    return f"t={timestamp},v1={_expected(timestamp, payload, secret)}"


def test_compute_signature_matches_reference() -> None:
    ts = 1_614_556_800
    assert compute_signature(ts, PAYLOAD, SECRET) == _expected(ts, PAYLOAD, SECRET)


def test_compute_signature_known_value() -> None:
    # Frozen known-good vector so a regression in the HMAC scheme is caught.
    assert (
        compute_signature(1700000000, "hello", "whsec_x")
        == "20d8679b715783336aef8d9fff251ed21322d839b1f5de36998c6130fdee4d9f"
    )


def test_valid_signature_accepts() -> None:
    ts = 2_000_000_000
    assert verify_signature(PAYLOAD, _header(ts), SECRET, now=ts) == ts


def test_bytes_payload_accepts() -> None:
    ts = 2_000_000_000
    header = _header(ts)
    assert verify_signature(PAYLOAD.encode(), header, SECRET, now=ts) == ts


def test_tampered_payload_rejected() -> None:
    ts = 2_000_000_000
    header = _header(ts)
    with pytest.raises(SignatureVerificationError, match="no signatures match"):
        verify_signature(PAYLOAD + " ", header, SECRET, now=ts)


def test_wrong_secret_rejected() -> None:
    ts = 2_000_000_000
    with pytest.raises(SignatureVerificationError):
        verify_signature(PAYLOAD, _header(ts), "whsec_wrong", now=ts)


def test_expired_timestamp_rejected() -> None:
    ts = 2_000_000_000
    header = _header(ts)
    with pytest.raises(SignatureVerificationError, match="outside the tolerance"):
        verify_signature(PAYLOAD, header, SECRET, tolerance=300, now=ts + 10_000)


def test_tolerance_zero_disables_replay_check() -> None:
    ts = 1_000
    header = _header(ts)
    # Far in the future relative to ts, but tolerance=0 disables the window.
    assert verify_signature(PAYLOAD, header, SECRET, tolerance=0, now=ts + 10**9) == ts


def test_missing_timestamp_rejected() -> None:
    with pytest.raises(SignatureVerificationError, match="no timestamp"):
        verify_signature(PAYLOAD, "v1=deadbeef", SECRET)


def test_missing_v1_rejected() -> None:
    with pytest.raises(SignatureVerificationError, match="no v1 signatures"):
        verify_signature(PAYLOAD, "t=123", SECRET)


def test_non_integer_timestamp_rejected() -> None:
    with pytest.raises(SignatureVerificationError, match="invalid timestamp"):
        verify_signature(PAYLOAD, "t=notanumber,v1=abc", SECRET)


def test_multiple_v1_signatures_one_matches() -> None:
    ts = 2_000_000_000
    good = _expected(ts, PAYLOAD, SECRET)
    header = f"t={ts},v1=00deadbeef,v1={good}"
    assert verify_signature(PAYLOAD, header, SECRET, now=ts) == ts


def test_construct_event_returns_parsed_event() -> None:
    ts = 2_000_000_000
    event = construct_event(PAYLOAD, _header(ts), SECRET, now=ts)
    assert event.id == "evt_1"
    assert event.type == "checkout.session.completed"


def test_construct_event_rejects_bad_signature() -> None:
    ts = 2_000_000_000
    with pytest.raises(SignatureVerificationError):
        construct_event(PAYLOAD, f"t={ts},v1=00", SECRET, now=ts)
