"""Stripe webhook signature verification.

Stripe signs every webhook with a header of the form::

    Stripe-Signature: t=1614556800,v1=5257a8...,v1=a83d9f...

The signed payload is the string ``"{timestamp}.{body}"`` and the expected
signature is ``HMAC-SHA256(signing_secret, signed_payload)`` rendered as lower
case hexadecimal. This module reproduces that scheme exactly: it parses the
header, recomputes the HMAC, performs a constant-time comparison against every
``v1`` signature offered, and rejects events whose timestamp is older than a
configurable tolerance (replay protection).

Part of Stripe Webhook Handler by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

import hashlib
import hmac
import time

from stripe_webhook_handler.errors import SignatureVerificationError
from stripe_webhook_handler.models import StripeEvent

DEFAULT_TOLERANCE_SECONDS = 300
"""Default replay window, matching Stripe's own SDK (5 minutes)."""

_SCHEME = "v1"


def compute_signature(timestamp: int, payload: str | bytes, secret: str) -> str:
    """Compute the expected ``v1`` HMAC-SHA256 signature for a payload.

    Args:
        timestamp: The UNIX timestamp that prefixes the signed payload.
        payload: The exact webhook request body.
        secret: The endpoint signing secret (``whsec_...``).

    Returns:
        The signature as a lower-case hex digest.
    """
    body = payload.encode("utf-8") if isinstance(payload, str) else payload
    signed_payload = b"%d.%s" % (timestamp, body)
    return hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()


def _parse_header(header: str) -> tuple[int, list[str]]:
    """Parse a ``Stripe-Signature`` header into a timestamp and signatures.

    Args:
        header: The raw header value (``t=...,v1=...``).

    Returns:
        A tuple of ``(timestamp, [v1_signatures])``.

    Raises:
        SignatureVerificationError: If the header is malformed or missing parts.
    """
    timestamp: int | None = None
    signatures: list[str] = []
    for item in header.split(","):
        key, _, value = item.partition("=")
        key, value = key.strip(), value.strip()
        if not value:
            continue
        if key == "t":
            try:
                timestamp = int(value)
            except ValueError as exc:
                raise SignatureVerificationError("invalid timestamp in signature header") from exc
        elif key == _SCHEME:
            signatures.append(value)
    if timestamp is None:
        raise SignatureVerificationError("no timestamp found in signature header")
    if not signatures:
        raise SignatureVerificationError("no v1 signatures found in signature header")
    return timestamp, signatures


def verify_signature(
    payload: str | bytes,
    sig_header: str,
    secret: str,
    *,
    tolerance: int = DEFAULT_TOLERANCE_SECONDS,
    now: int | None = None,
) -> int:
    """Verify a Stripe webhook signature.

    Args:
        payload: The exact request body bytes/text Stripe delivered.
        sig_header: The value of the ``Stripe-Signature`` header.
        secret: The endpoint signing secret (``whsec_...``).
        tolerance: Maximum allowed age, in seconds, of the signed timestamp.
            Pass ``0`` or a negative value to disable the replay check.
        now: Override the current time (UNIX seconds) — useful for tests.

    Returns:
        The verified timestamp from the header.

    Raises:
        SignatureVerificationError: If no offered signature matches, or the
            timestamp is outside the tolerance window.
    """
    timestamp, signatures = _parse_header(sig_header)
    expected = compute_signature(timestamp, payload, secret)

    # Constant-time comparison against every offered signature. We iterate over
    # all of them (rather than short-circuiting) so timing does not leak which
    # candidate matched.
    matched = False
    for candidate in signatures:
        if hmac.compare_digest(expected, candidate):
            matched = True
    if not matched:
        raise SignatureVerificationError("no signatures match the expected value")

    if tolerance > 0:
        current = int(time.time()) if now is None else now
        if timestamp < current - tolerance:
            raise SignatureVerificationError(
                f"timestamp {timestamp} is outside the tolerance of {tolerance}s"
            )

    return timestamp


def construct_event(
    payload: str | bytes,
    sig_header: str,
    secret: str,
    *,
    tolerance: int = DEFAULT_TOLERANCE_SECONDS,
    now: int | None = None,
) -> StripeEvent:
    """Verify a signature and parse the payload into a :class:`StripeEvent`.

    This is the recommended entry point: it mirrors Stripe's own
    ``Webhook.construct_event`` and guarantees a returned event has been
    cryptographically verified.

    Args:
        payload: The exact request body bytes/text Stripe delivered.
        sig_header: The value of the ``Stripe-Signature`` header.
        secret: The endpoint signing secret (``whsec_...``).
        tolerance: Maximum allowed age, in seconds, of the signed timestamp.
        now: Override the current time (UNIX seconds) — useful for tests.

    Returns:
        The verified, parsed event.

    Raises:
        SignatureVerificationError: If verification fails.
        ValueError: If the payload is not a valid Stripe event object.
    """
    verify_signature(payload, sig_header, secret, tolerance=tolerance, now=now)
    return StripeEvent.from_payload(payload)
