"""Idempotent Stripe webhook handler — signature verification and event routing.

Part of Stripe Webhook Handler by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

from stripe_webhook_handler.errors import (
    SignatureVerificationError,
    WebhookError,
)
from stripe_webhook_handler.handler import WebhookHandler
from stripe_webhook_handler.idempotency import IdempotencyStore, InMemoryIdempotencyStore
from stripe_webhook_handler.models import StripeEvent
from stripe_webhook_handler.signature import construct_event, verify_signature

__version__ = "0.1.0"

__all__ = [
    "IdempotencyStore",
    "InMemoryIdempotencyStore",
    "SignatureVerificationError",
    "StripeEvent",
    "WebhookError",
    "WebhookHandler",
    "__version__",
    "construct_event",
    "verify_signature",
]
