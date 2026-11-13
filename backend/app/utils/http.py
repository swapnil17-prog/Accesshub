"""Request parsing helpers for route functions."""

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
