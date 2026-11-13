"""Request parsing and response helpers for route functions."""

from typing import Any

from flask import request
from marshmallow import Schema

from ..errors import InvalidInputError


def load_json(schema: Schema) -> dict[str, Any]:
    """Validate the JSON body with ``schema``; a missing or non-object body is a 422."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise InvalidInputError("Request body must be a JSON object")
    return schema.load(data)


def load_json_optional(schema: Schema) -> dict[str, Any]:
    """Like load_json, but an empty body counts as ``{}``."""
    if not request.get_data():
        return schema.load({})
    return load_json(schema)


def load_args(schema: Schema) -> dict[str, Any]:
    """Validate the query string with ``schema`` (422 on bad values)."""
    return schema.load(request.args.to_dict())


def paginated(items: list[Any], page: int, per_page: int, total: int) -> dict[str, Any]:
    """The API's pagination envelope."""
    return {"items": items, "page": page, "per_page": per_page, "total": total}
