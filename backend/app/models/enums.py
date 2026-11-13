"""Enumerations shared by models, services and schemas."""

from enum import StrEnum


class RoleName(StrEnum):
    EMPLOYEE = "employee"
    MANAGER = "manager"
    APP_OWNER = "app_owner"
    ADMIN = "admin"
    AUDITOR = "auditor"


class ApproverType(StrEnum):
    MANAGER = "MANAGER"
    APP_OWNER = "APP_OWNER"
    SPECIFIC_USER = "SPECIFIC_USER"


class RequestStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class Decision(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SKIPPED = "SKIPPED"


class AuditAction(StrEnum):
    """Values written to audit_logs.action. Add new actions here, never free-form strings."""

    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILED = "LOGIN_FAILED"
    LOGOUT = "LOGOUT"
    REQUEST_CREATED = "REQUEST_CREATED"
    REQUEST_ADVANCED = "REQUEST_ADVANCED"
    REQUEST_APPROVED = "REQUEST_APPROVED"
    REQUEST_REJECTED = "REQUEST_REJECTED"
    REQUEST_CANCELLED = "REQUEST_CANCELLED"
    REQUEST_EXPIRED = "REQUEST_EXPIRED"
    APPROVAL_ASSIGNED = "APPROVAL_ASSIGNED"
    APPROVAL_APPROVED = "APPROVAL_APPROVED"
    APPROVAL_REJECTED = "APPROVAL_REJECTED"
    APPROVAL_SKIPPED = "APPROVAL_SKIPPED"
    APPROVAL_ESCALATED = "APPROVAL_ESCALATED"
    APPROVAL_REASSIGNED = "APPROVAL_REASSIGNED"
