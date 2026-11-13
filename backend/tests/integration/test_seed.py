"""`flask seed` tests. Seeding is the slowest thing in the suite, so each test seeds once
and checks several properties."""

from collections import Counter

from sqlalchemy import func, select

from app.models import AccessRequest, Application, Approval, Decision, RequestStatus, User
from app.seed import DEMO_PASSWORD


def _seed(app) -> str:
    result = app.test_cli_runner().invoke(args=["seed"])
    assert result.exit_code == 0, result.output
    return result.output


def _counts(db) -> dict[str, int]:
    db.session.expire_all()
    return {
        model.__name__: db.session.scalar(select(func.count()).select_from(model))
        for model in (User, Application, AccessRequest, Approval)
    }


def test_seed_creates_consistent_demo_data_and_is_idempotent(app, db):
    _seed(app)
    first = _counts(db)
    assert first["User"] == 15
    assert first["Application"] == 5
    assert first["AccessRequest"] == 40

    statuses = Counter(db.session.scalars(select(AccessRequest.status)))
    assert set(statuses) == set(RequestStatus), "every status is represented"

    for app_ in db.session.scalars(select(Application)):
        assert 2 <= len(app_.access_levels) <= 3
        assert 1 <= len(app_.workflow_steps) <= 3
        assert [s.step_order for s in app_.workflow_steps] == list(range(1, len(app_.workflow_steps) + 1))

    for req in db.session.scalars(select(AccessRequest)):
        pending = [a for a in req.approvals if a.decision == Decision.PENDING]
        if req.status == RequestStatus.PENDING:
            assert len(pending) == 1 and pending[0].step_order == req.current_step
        else:
            assert pending == []
        assert all(a.approver_id != req.requester_id for a in req.approvals), "no self-approval"
        if req.status == RequestStatus.EXPIRED:
            assert req.expires_at is not None

    output = _seed(app)
    assert "requests_created_this_run: 0" in output
    assert _counts(db) == first


def test_demo_accounts_can_log_in_with_expected_roles(app, client, db):
    _seed(app)
    expected = {
        "admin": "admin",
        "auditor": "auditor",
        "manager": "manager",
        "owner": "app_owner",
        "employee": "employee",
    }
    for local, role in expected.items():
        resp = client.post(
            "/api/auth/login", json={"email": f"{local}@accesshub.dev", "password": DEMO_PASSWORD}
        )
        assert resp.status_code == 200, local
        assert role in resp.get_json()["user"]["roles"]
