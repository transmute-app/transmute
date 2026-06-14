from fastapi.testclient import TestClient

from api.routes.oidc import _coerce_username_claim


def _capture_redirect_uri(monkeypatch, tmp_path, app_url):
    """Drive GET /api/oidc/login with OIDC configured and authlib mocked,
    returning the redirect_uri the app would send to the provider."""
    monkeypatch.setenv("APP_URL", app_url)
    monkeypatch.setenv("OIDC_ISSUER_URL", "https://idp.example.com/realms/x")
    monkeypatch.setenv("OIDC_CLIENT_ID", "transmute")
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "secret")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    from core.settings import get_settings
    get_settings.cache_clear()

    import api.routes.oidc as oidc_mod
    monkeypatch.setattr(oidc_mod, "_oauth", None)
    monkeypatch.setattr(oidc_mod, "_metadata_cache", None)

    async def fake_load_metadata():
        return {"authorization_endpoint": "https://idp.example.com/realms/x/auth"}

    monkeypatch.setattr(oidc_mod, "_load_metadata", fake_load_metadata)

    captured = {}

    async def fake_authorize_redirect(request, redirect_uri, **kwargs):
        from starlette.responses import RedirectResponse
        captured["redirect_uri"] = redirect_uri
        return RedirectResponse(url="https://idp.example.com/auth")

    oauth = oidc_mod._get_oauth()
    monkeypatch.setattr(oauth.oidc, "authorize_redirect", fake_authorize_redirect)

    import main
    client = TestClient(main.create_app(), follow_redirects=False)
    client.get("/api/oidc/login")
    get_settings.cache_clear()
    return captured["redirect_uri"]


def test_oidc_redirect_uri_under_subpath(monkeypatch, tmp_path):
    # Regression: url_for already includes the root_path, so combining it with
    # app_url's full value used to double the sub-path (/transmute/transmute/...).
    uri = _capture_redirect_uri(monkeypatch, tmp_path, "https://example.com/transmute")
    assert uri == "https://example.com/transmute/api/oidc/callback"


def test_oidc_redirect_uri_at_root(monkeypatch, tmp_path):
    uri = _capture_redirect_uri(monkeypatch, tmp_path, "https://example.com")
    assert uri == "https://example.com/api/oidc/callback"


def test_coerce_username_claim_normalizes_supported_values():
    assert _coerce_username_claim("  alice  ") == "alice"
    assert _coerce_username_claim(["  eng ", " staff "]) == "eng.staff"
    assert _coerce_username_claim(True) == "True"


def test_coerce_username_claim_rejects_empty_and_object_values():
    assert _coerce_username_claim("   ") is None
    assert _coerce_username_claim([]) is None
    assert _coerce_username_claim({"nested": "value"}) is None