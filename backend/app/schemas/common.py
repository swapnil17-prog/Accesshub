"""Shared schema pieces: brief nested objects, pagination, flexible date parsing."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from marshmallow import EXCLUDE, Schema, ValidationError, fields, validate

from .base import BaseSchema


class FlexibleDateTime(fields.Field):
    """Accepts ``YYYY-MM-DD`` or an ISO datetime; naive values are treated as UTC.

    With ``end_of_day=True`` a bare date means "through the end of that day" and becomes the
    *next* midnight, so callers filter with ``< value``.
    """

    default_error_messages = {"invalid": "Not a valid date or datetime."}  # noqa: RUF012

    def __init__(self, *, end_of_day: bool = False, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.end_of_day = end_of_day

    def _deserialize(self, value: Any, attr: str | None, data: Any, **kwargs: Any) -> datetime:
        if not isinstance(value, str):
            raise self.make_error("invalid")
        try:
            if len(value) == 10:
                day = date.fromisoformat(value)
                result = datetime(day.year, day.month, day.day, tzinfo=UTC)
                return result + timedelta(days=1) if self.end_of_day else result
            result = datetime.fromisoformat(value)
        except ValueError as exc:
            raise self.make_error("invalid") from exc
        return result if result.tzinfo else result.replace(tzinfo=UTC)


class UserBriefSchema(BaseSchema):
    id = fields.Integer()
    name = fields.String()
    email = fields.String()


class NamedRefSchema(BaseSchema):
    id = fields.Integer()
    name = fields.String()


class QuerySchema(Schema):
    """Base for query-string schemas: unknown params (e.g. cache busters) are ignored."""

    class Meta:
        unknown = EXCLUDE


class PaginationQuerySchema(QuerySchema):
    page = fields.Integer(load_default=1, validate=validate.Range(min=1))
    per_page = fields.Integer(load_default=20, validate=validate.Range(min=1, max=100))


def not_blank(min_length: int):
    """Validator: at least ``min_length`` characters once surrounding whitespace is removed."""

    def _check(value: str) -> None:
        if len(value.strip()) < min_length:
            raise ValidationError(f"Must be at least {min_length} characters.")

    return _check
