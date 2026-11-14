"""Pagination for list queries (shape matches the API envelope)."""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import Select

from ..extensions import db


@dataclass
class Page:
    items: list[Any]
    page: int
    per_page: int
    total: int


def paginate(stmt: Select, page: int, per_page: int) -> Page:
    result = db.paginate(stmt, page=page, per_page=per_page, error_out=False, count=True)
    return Page(items=list(result.items), page=page, per_page=per_page, total=result.total or 0)


def like_pattern(term: str) -> str:
    """``%term%`` with LIKE wildcards in the user's input escaped (use with escape='\\\\')."""
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"
