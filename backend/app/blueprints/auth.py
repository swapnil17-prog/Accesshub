"""/api/auth: login, refresh, logout, me."""

from flask import Blueprint, request
from flask_jwt_extended import get_jwt, jwt_required

from ..schemas.auth import LoginSchema, LogoutSchema
from ..schemas.user import UserSchema
from ..services import auth as auth_service
from ..utils.decorators import get_current_user
from ..utils.http import load_json

auth_bp = Blueprint("auth", __name__)

_login_schema = LoginSchema()
_logout_schema = LogoutSchema()
_user_schema = UserSchema()


@auth_bp.post("/login")
def login():
    data = load_json(_login_schema)
    user = auth_service.authenticate(data["email"], data["password"])
    tokens = auth_service.issue_tokens(user)
    return {**tokens, "token_type": "Bearer", "user": _user_schema.dump(user)}


@auth_bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    return {"access_token": auth_service.refresh_access_token(get_current_user()), "token_type": "Bearer"}


@auth_bp.post("/logout")
@jwt_required()
def logout():
    body = request.get_json(silent=True) or {}
    data = _logout_schema.load(body)
    auth_service.logout(get_current_user(), get_jwt(), data["refresh_token"])
    return {"message": "Logged out"}


@auth_bp.get("/me")
@jwt_required()
def me():
    return _user_schema.dump(get_current_user())
