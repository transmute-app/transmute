import sys
import types

from fastapi.testclient import TestClient


def _ensure_optional_native_stubs():
    """Allow importing the app without WeasyPrint system libraries (Windows CI/dev)."""
    if "weasyprint" not in sys.modules:
        stub = types.ModuleType("weasyprint")
        stub.HTML = object
        sys.modules["weasyprint"] = stub


def _make_client(monkeypatch, tmp_path, **env):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AUTH_SECRET_KEY", "test-secret-key")
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    _ensure_optional_native_stubs()

    from core.settings import get_settings
    get_settings.cache_clear()

    import main
    from api import deps

    deps._user_db.cache_clear()
    deps._file_db.cache_clear()
    deps._settings_db.cache_clear()

    return TestClient(main.create_app())


def test_header_authenticate_auto_creates_user(monkeypatch, tmp_path):
    client = _make_client(
        monkeypatch,
        tmp_path,
        HEADER_AUTH_ENABLED="true",
        HEADER_AUTH_AUTO_CREATE="true",
    )

    response = client.post(
        "/api/users/header-authenticate",
        headers={
            "X-Forwarded-User": "alice",
            "X-Forwarded-Email": "alice@example.com",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["username"] == "alice"
    assert body["user"]["email"] == "alice@example.com"
    assert body["user"]["role"] == "admin"
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["expires_in"] > 0


def test_header_auth_protects_me_endpoint(monkeypatch, tmp_path):
    client = _make_client(
        monkeypatch,
        tmp_path,
        HEADER_AUTH_ENABLED="true",
        HEADER_AUTH_AUTO_CREATE="true",
    )

    me = client.get(
        "/api/users/me",
        headers={"X-Forwarded-User": "bob"},
    )
    assert me.status_code == 200
    assert me.json()["username"] == "bob"


def test_header_authenticate_disabled_returns_401(monkeypatch, tmp_path):
    client = _make_client(monkeypatch, tmp_path, HEADER_AUTH_ENABLED="false")

    response = client.post(
        "/api/users/header-authenticate",
        headers={"X-Forwarded-User": "alice"},
    )
    assert response.status_code == 401


def test_header_auth_custom_headers_and_public_signup(monkeypatch, tmp_path):
    client = _make_client(
        monkeypatch,
        tmp_path,
        HEADER_AUTH_ENABLED="true",
        HEADER_AUTH_AUTO_CREATE="false",
        ALLOW_PUBLIC_SIGNUP="true",
        HEADER_AUTH_USERNAME_HEADER="X-Auth-User",
        HEADER_AUTH_EMAIL_HEADER="X-Auth-Email",
    )

    response = client.post(
        "/api/users/header-authenticate",
        headers={
            "X-Auth-User": "carol",
            "X-Auth-Email": "carol@example.com",
        },
    )
    assert response.status_code == 200
    assert response.json()["user"]["username"] == "carol"


def test_header_auth_rejects_unknown_user_without_auto_create(monkeypatch, tmp_path):
    client = _make_client(
        monkeypatch,
        tmp_path,
        HEADER_AUTH_ENABLED="true",
        HEADER_AUTH_AUTO_CREATE="false",
        ALLOW_PUBLIC_SIGNUP="false",
    )

    response = client.post(
        "/api/users/header-authenticate",
        headers={"X-Forwarded-User": "nobody"},
    )
    assert response.status_code == 401
