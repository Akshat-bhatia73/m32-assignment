"""Smoke tests that don't require a database connection."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_openapi_lists_core_routes():
    paths = client.get("/openapi.json").json()["paths"]
    for expected in [
        "/auth/signup",
        "/auth/login",
        "/chat/stream",
        "/sessions",
        "/integrations/status",
        "/calendar/events",
        "/org",
        "/org/invites",
    ]:
        assert expected in paths


def test_chat_requires_auth():
    res = client.post(
        "/chat/stream",
        json={"session_id": "00000000-0000-0000-0000-000000000000", "message": "hi"},
    )
    assert res.status_code == 401
