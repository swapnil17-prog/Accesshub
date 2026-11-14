"""Email notifications (Flask-Mail + Jinja2 HTML and plain-text templates).

Contract with callers:
* call :func:`notify` only **after** the business transaction has committed;
* :func:`notify` never raises: a rendering or SMTP failure is logged and the decision
  that triggered it stands. (Production could hand messages to a queue instead; the
  call sites would not change.)

Templates live in ``app/templates/email/<event>.{txt,html}``. Every email carries a deep
link into the frontend built from ``FRONTEND_URL``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any

from flask import current_app, render_template
from flask_mail import Message

from ..extensions import mail

if TYPE_CHECKING:
    from ..models import AccessRequest, User

logger = logging.getLogger(__name__)

APPROVAL_NEEDED = "approval_needed"
REQUEST_APPROVED = "request_approved"
REQUEST_REJECTED = "request_rejected"
APPROVAL_ESCALATED = "approval_escalated"
ACCESS_EXPIRING = "access_expiring"
ACCESS_EXPIRED = "access_expired"


def _what(r: AccessRequest) -> str:
    return f"{r.application.name} - {r.access_level.name}"


SUBJECTS: dict[str, Callable[[AccessRequest, dict[str, Any]], str]] = {
    APPROVAL_NEEDED: lambda r, _c: f"Approval needed: {_what(r)} for {r.requester.name}",
    REQUEST_APPROVED: lambda r, _c: f"Approved: {_what(r)}",
    REQUEST_REJECTED: lambda r, _c: f"Rejected: {_what(r)}",
    APPROVAL_ESCALATED: lambda r, _c: f"Escalated: {r.requester.name}'s request for {_what(r)}",
    ACCESS_EXPIRING: lambda r, c: f"Your {_what(r)} access expires in {c['days_left']} day(s)",
    ACCESS_EXPIRED: lambda r, _c: f"Your {_what(r)} access has expired",
}


def frontend_link(path: str) -> str:
    return current_app.config["FRONTEND_URL"].rstrip("/") + path


def build_message(event: str, request: AccessRequest, recipient: User, **extra: Any) -> Message:
    """Render one email for one recipient (also used by tests and previews)."""
    context = {
        "event": event,
        "request": request,
        "recipient": recipient,
        "request_link": frontend_link(f"/requests/{request.id}"),
        "inbox_link": frontend_link("/approvals"),
        "app_name": "AccessHub",
        **extra,
    }
    subject = f"[AccessHub] {SUBJECTS[event](request, context)}"
    return Message(
        subject=subject,
        recipients=[recipient.email],
        body=render_template(f"email/{event}.txt", **context),
        html=render_template(f"email/{event}.html", **context),
    )


def notify(event: str, request: AccessRequest, recipients: Sequence[User], **extra: Any) -> None:
    """Email each active recipient about ``event`` on ``request``. Never raises."""
    if event not in SUBJECTS:
        logger.error("Unknown notification event %r", event)
        return
    seen: set[int] = set()
    for recipient in recipients:
        if recipient is None or not recipient.is_active or recipient.id in seen:
            continue
        seen.add(recipient.id)
        try:
            mail.send(build_message(event, request, recipient, **extra))
            logger.info("Sent %s for request %s to %s", event, request.id, recipient.email)
        except Exception:
            logger.exception("Failed to send %s for request %s to %s", event, request.id, recipient.email)
