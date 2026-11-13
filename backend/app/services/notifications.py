"""Notifications. Phase 2 stub: logs only. Phase 4 replaces the body with real emails.

The workflow engine calls :func:`notify` only after its transaction has committed, and
swallows any exception from it, so a notification problem can never undo a decision.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import AccessRequest, User

logger = logging.getLogger(__name__)

APPROVAL_NEEDED = "approval_needed"
REQUEST_APPROVED = "request_approved"
REQUEST_REJECTED = "request_rejected"


def notify(event: str, request: AccessRequest, recipients: Sequence[User]) -> None:
    """Tell ``recipients`` that ``event`` happened to ``request``."""
    logger.info(
        "notify event=%s request_id=%s recipients=%s",
        event,
        request.id,
        [user.email for user in recipients],
    )
