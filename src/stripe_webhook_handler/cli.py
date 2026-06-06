"""Command-line interface for Stripe Webhook Handler.

``stripe-webhook-handler demo`` signs a sample event with a test secret, then
verifies and dispatches it twice to show signature checking, routing, and
idempotency — all fully offline.

Part of Stripe Webhook Handler by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

import json
import time

import typer
from rich.console import Console

from stripe_webhook_handler import __version__
from stripe_webhook_handler.errors import SignatureVerificationError
from stripe_webhook_handler.handler import DispatchStatus, WebhookHandler
from stripe_webhook_handler.models import StripeEvent
from stripe_webhook_handler.signature import compute_signature

app = typer.Typer(add_completion=False, help="Stripe Webhook Handler — by Viprasol Tech.")
console = Console()

_SECRET = "whsec_demo_secret_do_not_use_in_production"


def _sample_payload(event_id: str = "evt_1Demo0001") -> str:
    """Build a deterministic ``checkout.session.completed`` payload."""
    return json.dumps(
        {
            "id": event_id,
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_123",
                    "amount_total": 4200,
                    "currency": "usd",
                    "customer_email": "buyer@example.com",
                }
            },
        }
    )


def _sign(payload: str, timestamp: int) -> str:
    """Build a valid ``Stripe-Signature`` header for ``payload``."""
    sig = compute_signature(timestamp, payload, _SECRET)
    return f"t={timestamp},v1={sig}"


@app.command()
def version() -> None:
    """Print the installed version."""
    console.print(f"stripe-webhook-handler [bold cyan]{__version__}[/] — by Viprasol Tech")


@app.command()
def demo() -> None:
    """Verify and dispatch a sample event offline (twice, to show dedupe)."""
    payload = _sample_payload()
    timestamp = int(time.time())
    sig_header = _sign(payload, timestamp)

    handler = WebhookHandler(_SECRET)

    @handler.register("checkout.session.completed")
    def _fulfil(event: StripeEvent) -> None:
        obj = event.object
        cents = int(obj.get("amount_total", 0))
        console.print(
            f"  -> fulfilling order for [bold]{obj.get('customer_email', '?')}[/] "
            f"(${cents / 100:.2f} {str(obj.get('currency', '')).upper()})"
        )

    console.print("[bold]1. Valid signature, first delivery[/]")
    status = handler.handle(payload, sig_header)
    console.print(f"   status: [green]{status.value}[/]")

    console.print("[bold]2. Same event id redelivered (Stripe retry)[/]")
    status = handler.handle(payload, sig_header)
    console.print(f"   status: [yellow]{status.value}[/]")

    console.print("[bold]3. Tampered payload (amount changed by attacker)[/]")
    tampered = payload.replace("4200", "1")
    try:
        handler.handle(tampered, sig_header)
        console.print("   [red]ERROR: tampered payload was accepted![/]")
        raise typer.Exit(code=1)
    except SignatureVerificationError as exc:
        console.print(f"   rejected: [green]{exc}[/]")

    console.print("[bold]4. Expired timestamp (replay outside tolerance)[/]")
    old_ts = timestamp - 10_000
    old_header = _sign(payload, old_ts)
    other = WebhookHandler(_SECRET)
    try:
        other.handle(payload, old_header)
        console.print("   [red]ERROR: expired event was accepted![/]")
        raise typer.Exit(code=1)
    except SignatureVerificationError as exc:
        console.print(f"   rejected: [green]{exc}[/]")

    console.print("[bold]5. Unknown event type (no handler registered)[/]")
    unknown = json.dumps({"id": "evt_unknown_01", "type": "ping", "data": {}})
    unknown_header = _sign(unknown, timestamp)
    status = handler.handle(unknown, unknown_header)
    console.print(f"   status: [cyan]{status.value}[/] (returned 200, no retry)")

    assert status is DispatchStatus.IGNORED
    console.print("\n[bold green]Demo complete - all checks behaved as expected.[/]")


if __name__ == "__main__":
    app()
