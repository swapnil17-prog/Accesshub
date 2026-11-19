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

    @app.cli.command("run-scheduler")
    def run_scheduler_command() -> None:
        """Run the background jobs until stopped (command of the dedicated scheduler container).

        Requires RUN_SCHEDULER=1. Exactly one such process should run; the web containers keep
        RUN_SCHEDULER=0. Stops cleanly on SIGTERM (docker stop) or Ctrl+C.
        """
        import signal
        import threading

        from . import scheduler as scheduler_module

        if not app.config.get("RUN_SCHEDULER"):
            raise click.ClickException("Set RUN_SCHEDULER=1 to run the scheduler process.")
        scheduler_module.init_scheduler(app)  # no-op if create_app already started it
        running = scheduler_module.scheduler
        if not running.running:
            raise click.ClickException("The scheduler did not start (is this the testing config?).")

        stop = threading.Event()
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: stop.set())
        click.echo("Scheduler running jobs: " + ", ".join(job.id for job in running.get_jobs()))
        stop.wait()
        running.shutdown(wait=True)
        click.echo("Scheduler stopped.")
