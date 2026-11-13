"""Application exceptions and the single place they are mapped to JSON HTTP errors.

Every error response has the shape::

    {"error": {"code": "...", "message": "...", "details": {...}}}

Services raise subclasses of :class:`AppError`; they never build HTTP responses themselves.
"""

from __future__ import annotations

from typing import Any

from flask import Flask, Response, current_app, jsonify
from marshmallow import ValidationError as MarshmallowValidationError
from werkzeug.exceptions import HTTPException, InternalServerError


class AppError(Exception):
    status_code: int = 400
    code: str = "BAD_REQUEST"
    message: str = "Bad request"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.details = details or {}
        super().__init__(self.message)


class InvalidInputError(AppError):
    status_code = 422
    code = "VALIDATION_ERROR"
    message = "Invalid input"


class UnauthorizedError(AppError):
    status_code = 401
    code = "UNAUTHORIZED"
    message = "Authentication required"


class InvalidCredentialsError(UnauthorizedError):
    code = "INVALID_CREDENTIALS"
    message = "Invalid email or password"


class ForbiddenError(AppError):
    status_code = 403
    code = "FORBIDDEN"
    message = "You do not have permission to perform this action"


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"
    message = "Resource not found"


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"
    message = "Conflict with the current state of the resource"


# --- Workflow domain errors (raised by services, mapped to HTTP by the handlers below) ---


class DuplicateRequestError(ConflictError):
    code = "DUPLICATE_REQUEST"
    message = "You already have a pending request for this application and access level"


class NotAuthorizedError(ForbiddenError):
    """The user is authenticated and has the role, but may not act on this object."""

    code = "NOT_AUTHORIZED"
    message = "You are not allowed to act on this item"


class InvalidStateError(ConflictError):
    code = "INVALID_STATE"
    message = "This action is not allowed in the item's current state"


def error_response(
    status: int, code: str, message: str, details: dict[str, Any] | None = None
) -> tuple[Response, int]:
    return jsonify(error={"code": code, "message": message, "details": details or {}}), status


def _http_code_name(exc: HTTPException) -> str:
    return (exc.name or "HTTP_ERROR").upper().replace(" ", "_").replace("'", "")


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(AppError)
    def handle_app_error(exc: AppError):
        return error_response(exc.status_code, exc.code, exc.message, exc.details)

    @app.errorhandler(MarshmallowValidationError)
    def handle_validation_error(exc: MarshmallowValidationError):
        details = exc.messages if isinstance(exc.messages, dict) else {"_schema": exc.messages}
        return error_response(422, "VALIDATION_ERROR", "Invalid input", details)

    @app.errorhandler(HTTPException)
    def handle_http_exception(exc: HTTPException):
        response, status = error_response(exc.code or 500, _http_code_name(exc), exc.description or "")
        if exc.code == 405 and getattr(exc, "valid_methods", None):
            response.headers["Allow"] = ", ".join(exc.valid_methods)
        return response, status

    @app.errorhandler(InternalServerError)
    def handle_internal_error(exc: InternalServerError):
        original = getattr(exc, "original_exception", None)
        if original is not None:
            current_app.logger.error("Unhandled exception", exc_info=original)
        return error_response(500, "INTERNAL_ERROR", "An unexpected error occurred")
