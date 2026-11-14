"""Custom `flask` CLI commands."""

import click
from flask import Flask


def register_cli(app: Flask) -> None:
    @app.cli.command("seed")
    def seed_command() -> None:
        """Load demo data (idempotent)."""
        from .seed import DEMO_PASSWORD, seed_demo_data

        summary = seed_demo_data()
        for key, value in summary.items():
            click.echo(f"{key:>26}: {value}")
        click.echo(f"Demo password for all seeded users: {DEMO_PASSWORD}")

    @app.cli.command("escalate")
    def escalate_command() -> None:
        """Escalate overdue approvals now (same as the 15-minute job)."""
        from .services.escalation import escalate_overdue

        click.echo(f"Escalated {escalate_overdue()} approval(s).")

    @app.cli.command("expire")
    def expire_command() -> None:
        """Expire ended access and send expiry reminders now (same as the daily job)."""
        from .services.escalation import run_daily

        result = run_daily()
        click.echo(f"Expired {result['expired']} request(s); sent {result['reminded']} reminder(s).")
