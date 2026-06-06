"""Typed models for Stripe webhook events.

Part of Stripe Webhook Handler by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field


class StripeEvent(BaseModel):
    """A parsed Stripe event payload.

    Only the fields the handler relies on are modelled explicitly; the full
    decoded JSON object is kept in :attr:`raw` so handlers can read anything.

    Attributes:
        id: The unique event id (e.g. ``evt_1A2b3C``). Used for idempotency.
        type: The event type (e.g. ``checkout.session.completed``).
        data: The ``data`` object of the event (typically ``{"object": {...}}``).
        raw: The complete decoded JSON object of the event.
    """

    id: str
    type: str
    data: dict[str, Any] = Field(default_factory=dict)
    raw: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: str | bytes) -> StripeEvent:
        """Build a :class:`StripeEvent` from a raw JSON webhook body.

        Args:
            payload: The exact request body bytes/text Stripe delivered.

        Returns:
            The parsed event.

        Raises:
            ValueError: If the payload is not a JSON object or lacks ``id``/``type``.
        """
        text = payload.decode("utf-8") if isinstance(payload, bytes) else payload
        obj: Any = json.loads(text)
        if not isinstance(obj, dict):
            raise ValueError("webhook payload must be a JSON object")
        if "id" not in obj or "type" not in obj:
            raise ValueError("webhook payload must contain 'id' and 'type'")
        return cls(
            id=str(obj["id"]),
            type=str(obj["type"]),
            data=obj.get("data", {}) if isinstance(obj.get("data"), dict) else {},
            raw=obj,
        )

    @property
    def object(self) -> dict[str, Any]:
        """Return ``data.object`` if present, else an empty dict."""
        inner = self.data.get("object")
        return inner if isinstance(inner, dict) else {}
