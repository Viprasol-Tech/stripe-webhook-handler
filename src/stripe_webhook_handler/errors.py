"""Exception types for the Stripe webhook handler.

Part of Stripe Webhook Handler by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations


class WebhookError(Exception):
    """Base class for all webhook-handling errors."""


class SignatureVerificationError(WebhookError):
    """Raised when a ``Stripe-Signature`` header fails verification.

    This covers a malformed header, a signature that does not match the
    computed HMAC, or a timestamp outside the allowed tolerance.
    """
