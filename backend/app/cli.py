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
