from app.extensions import db as _db


def test_health_ok(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok", "db": "ok"}


def test_health_reports_db_failure(client, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(_db.session, "execute", boom)
    resp = client.get("/api/health")
    assert resp.status_code == 503
    assert resp.get_json() == {"status": "degraded", "db": "error"}
