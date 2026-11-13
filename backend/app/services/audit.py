"""Audit trail writer.

``log_action`` adds a row to the *current* session and never commits: the caller commits it
together with the business change, so the audit entry and the change succeed or fail as one.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from flask import has_request_context, request

from ..extensions import db
from ..models import AuditLog, User

_UA_MAX = 512


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, set | frozenset):
        return sorted(value)
    return str(value)


def _to_json(value: dict[str, Any] | None) -> dict[str, Any] | None:
    """Round-trip through json so datetimes/enums are stored as plain JSON values."""
    if value is None:
        return None
    return json.loads(json.dumps(value, default=_json_default))


def log_action(
    actor: User | int | None,
    action: str,
    entity_type: str,
    entity_id: int | None,
    old: dict[str, Any] | None = None,
    new: dict[str, Any] | None = None,
) -> AuditLog:
    """Record an audit event in the current transaction.

    ``actor`` is the acting user (or their id); ``None`` means the system (scheduler, CLI).
    IP address and user agent are captured when called inside a request, otherwise left NULL.
    """
    ip_address: str | None = None
    user_agent: str | None = None
    if has_request_context():
        ip_address = request.remote_addr
        user_agent = (request.user_agent.string or None) and request.user_agent.string[:_UA_MAX]

    entry = AuditLog(
        action=str(action),
        entity_type=entity_type,
        entity_id=entity_id,
        old_value=_to_json(old),
        new_value=_to_json(new),
        ip_address=ip_address,
        user_agent=user_agent,
    )
    if isinstance(actor, User):
        entry.actor = actor  # works even if the user is not flushed yet
    else:
        entry.actor_id = actor
    db.session.add(entry)
    return entry
