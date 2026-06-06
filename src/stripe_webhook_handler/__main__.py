"""Module entry point so ``python -m stripe_webhook_handler`` runs the CLI.

Part of Stripe Webhook Handler by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

from stripe_webhook_handler.cli import app

if __name__ == "__main__":
    app()
