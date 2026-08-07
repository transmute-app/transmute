from fastapi.testclient import TestClient


def _make_client(monkeypatch, tmp_path, *, allow_public_signup: bool):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AUTH_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("ALLOW_PUBLIC_SIGNUP", "true" if allow_public_signup else "false")

    from core.settings import get_settings
    get_settings.cache_clear()

    import main
    from api import deps

    deps._user_db.cache_clear()
    deps._file_db.cache_clear()
    deps._settings_db.cache_clear()

    return TestClient(main.create_app())


def test_public_signup_creates_member_when_enabled(monkeypatch, tmp_path):
    client = _make_client(monkeypatch, tmp_path, allow_public_signup=True)

    bootstrap = client.post(
        "/api/users",
        json={
            "username": "admin",
            "password": "password123",
            "role": "member",
            "disabled": False,
        },
    )
    assert bootstrap.status_code == 201
    assert bootstrap.json()["role"] == "admin"

    status = client.get("/api/users/bootstrap-status")
    assert status.status_code == 200
    assert status.json()["allow_public_signup"] is True
    assert status.json()["requires_setup"] is False

    signup = client.post(
        "/api/users",
        json={
            "username": "member1",
            "password": "password123",
            "role": "admin",
            "disabled": True,
        },
    )
    assert signup.status_code == 201
    body = signup.json()
    assert body["username"] == "member1"
    assert body["role"] == "member"
    assert body["disabled"] is False


def test_public_signup_rejected_when_disabled(monkeypatch, tmp_path):
    client = _make_client(monkeypatch, tmp_path, allow_public_signup=False)

    bootstrap = client.post(
        "/api/users",
        json={
            "username": "admin",
            "password": "password123",
            "role": "member",
            "disabled": False,
        },
    )
    assert bootstrap.status_code == 201

    signup = client.post(
        "/api/users",
        json={
            "username": "member1",
            "password": "password123",
            "role": "member",
            "disabled": False,
        },
    )
    assert signup.status_code == 401
