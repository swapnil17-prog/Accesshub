"""Role matrix: every role is either allowed (2xx) or denied (403) on each protected endpoint."""

import pytest

from app.models import ApproverType
from tests.helpers import auth, make_app

ROLES = ["admin", "auditor", "manager", "owner", "employee"]
EVERYONE = set(ROLES)

# (method, url, body, roles allowed). {app} and {approval} are filled in per test.
CASES = [
    ("get", "/api/users", None, {"admin"}),
    ("get", "/api/users/lookup", None, {"admin", "owner"}),
    (
        "post",
        "/api/users",
        {"name": "New Person", "email": "new@example.com", "password": "Sup3rSecret!"},
        {"admin"},
    ),
    ("put", "/api/users/{employee}", {"department": "Ops"}, {"admin"}),
    ("put", "/api/users/{employee}/roles", {"roles": ["employee", "manager"]}, {"admin"}),
    ("get", "/api/audit", None, {"admin", "auditor"}),
    ("get", "/api/audit/export.csv", None, {"admin", "auditor"}),
    ("get", "/api/reports/summary", None, {"admin", "auditor"}),
    ("get", "/api/applications", None, EVERYONE),
    ("get", "/api/applications/{app}", None, EVERYONE),
    ("get", "/api/applications/{app}/workflow", None, EVERYONE),
    ("post", "/api/applications", {"name": "Brand New", "owner_id": "{owner_id}"}, {"admin"}),
    ("put", "/api/applications/{app}", {"description": "Updated"}, {"admin", "owner"}),
    ("delete", "/api/applications/{app}", None, {"admin"}),
    ("post", "/api/applications/{app}/access-levels", {"name": "Auditor"}, {"admin", "owner"}),
    (
        "put",
        "/api/applications/{app}/workflow",
        {"steps": [{"step_order": 1, "approver_type": "APP_OWNER", "sla_hours": 12}]},
        {"admin", "owner"},
    ),
    (
        "post",
        "/api/approvals/{approval}/reassign",
        {"approver_id": "{colleague_id}", "reason": "On leave"},
        {"admin"},
    ),
]


def _fill(value, ids):
    if isinstance(value, str):
        if value.startswith("{") and value.endswith("_id}"):
            return ids[value[1:-1]]
        return value.format(**ids)
    if isinstance(value, dict):
        return {k: _fill(v, ids) for k, v in value.items()}
    if isinstance(value, list):
        return [_fill(v, ids) for v in value]
    return value


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("method, url, body, allowed", CASES, ids=[f"{c[0]} {c[1]}" for c in CASES])
def test_role_matrix(client, org, role, method, url, body, allowed):
    application = make_app(org.owner, steps=[(ApproverType.MANAGER, None, 24)])
    created = client.post(
        "/api/requests",
        json={
            "application_id": application.id,
            "access_level_id": application.access_levels[0].id,
            "justification": "Needed for the migration project work.",
        },
        headers=auth(org.employee),
    ).get_json()
    ids = {
        "app": application.id,
        "approval": created["approvals"][0]["id"],
        "employee": org.employee.id,
        "owner_id": org.owner.id,
        "colleague_id": org.colleague.id,
    }
    user = {"admin": org.admin, "auditor": org.auditor, "manager": org.manager, "owner": org.owner}.get(
        role, org.employee
    )

    resp = getattr(client, method)(_fill(url, ids), json=_fill(body, ids), headers=auth(user))

    if role in allowed:
        assert 200 <= resp.status_code < 300, (role, resp.status_code, resp.get_data(as_text=True)[:300])
    else:
        assert resp.status_code == 403, (role, resp.status_code)
        assert resp.get_json()["error"]["code"] in {"FORBIDDEN", "NOT_AUTHORIZED"}


@pytest.mark.parametrize(
    "method, url, body",
    [
        ("put", "/api/applications/{app}", {"description": "Mine now"}),
        (
            "put",
            "/api/applications/{app}/workflow",
            {"steps": [{"step_order": 1, "approver_type": "MANAGER"}]},
        ),
        ("post", "/api/applications/{app}/access-levels", {"name": "Sneaky"}),
    ],
)
def test_app_owner_cannot_touch_someone_elses_app(client, org, method, url, body):
    other_owner_app = make_app(org.admin)  # owned by the admin, not by org.owner
    resp = getattr(client, method)(url.format(app=other_owner_app.id), json=body, headers=auth(org.owner))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "NOT_AUTHORIZED"


def test_owner_cannot_change_admin_only_fields(client, org):
    application = make_app(org.owner)
    for body in ({"owner_id": org.admin.id}, {"is_active": False}):
        resp = client.put(f"/api/applications/{application.id}", json=body, headers=auth(org.owner))
        assert resp.status_code == 403


def test_unauthenticated_is_401_everywhere(client, org):
    for method, url, *_ in CASES:
        resp = getattr(client, method)(url.format(app=1, approval=1, employee=1))
        assert resp.status_code == 401, (method, url)
