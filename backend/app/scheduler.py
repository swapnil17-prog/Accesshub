"""APScheduler wiring for the background jobs.

Started from create_app() only when RUN_SCHEDULER=1 and never under the testing config.
In production exactly one container sets RUN_SCHEDULER=1 (the "scheduler" service), so
web workers scaled to N replicas don't run the jobs N times. The jobs are idempotent
anyway, so an accidental double run is harmless.
"""

from __future__ import annotations

import logging
import os

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from flask import Flask

from .extensions import scheduler

logger = logging.getLogger(__name__)


def _in_reloader_parent(app: Flask) -> bool:
    """With `flask run --debug` the app is created twice; only the child serves requests."""
    return app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true"


def init_scheduler(app: Flask) -> None:
    if not app.config.get("RUN_SCHEDULER") or app.testing or _in_reloader_parent(app):
        return
    if scheduler.running:
        return

    from .services import escalation

    def escalate_job() -> None:
        with app.app_context():
            count = escalation.escalate_overdue()
            logger.info("Escalation job: %s approval(s) escalated", count)

    def daily_job() -> None:
        with app.app_context():
            result = escalation.run_daily()
            logger.info("Daily job: %s", result)

    common = {"replace_existing": True, "coalesce": True, "max_instances": 1, "misfire_grace_time": 300}
    scheduler.add_job(
        escalate_job,
        IntervalTrigger(minutes=app.config["ESCALATION_INTERVAL_MINUTES"]),
        id="escalate_overdue",
        **common,
    )
    scheduler.add_job(
        daily_job,
        CronTrigger(hour=app.config["DAILY_JOB_HOUR_UTC"], minute=0, timezone="UTC"),
        id="expire_and_remind",
        **common,
    )
    scheduler.start()
    logger.info("Scheduler started with jobs: %s", [job.id for job in scheduler.get_jobs()])
