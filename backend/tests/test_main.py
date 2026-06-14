import main as app_main


class DummySettings:
    def __init__(self, resolved_host, port=3313, has_conflict=False):
        self.port = port
        self._resolved_host = resolved_host
        self._has_conflict = has_conflict

    def resolved_bind_host(self):
        return self._resolved_host

    def has_host_override_conflict(self):
        return self._has_conflict


def test_run_api_server_uses_resolved_bind_host(monkeypatch):
    captured = {}

    def fake_run(app, host, port, log_config):
        captured["app"] = app
        captured["host"] = host
        captured["port"] = port
        captured["log_config"] = log_config

    monkeypatch.setattr(app_main.uvicorn, "run", fake_run)
    settings = DummySettings(["::", "0.0.0.0"], port=443)
    app = object()

    app_main.run_api_server(app, settings)

    assert captured["app"] is app
    assert captured["host"] == ["::", "0.0.0.0"]
    assert captured["port"] == 443
    assert isinstance(captured["log_config"], dict)


def test_run_api_server_logs_warning_on_host_override(monkeypatch, caplog):
    monkeypatch.setattr(app_main.uvicorn, "run", lambda *args, **kwargs: None)
    settings = DummySettings(["::", "0.0.0.0"], has_conflict=True)

    with caplog.at_level("WARNING"):
        app_main.run_api_server(object(), settings)

    assert "Both host and hosts are configured" in caplog.text


INDEX_HTML = (
    '<head>\n'
    '    <base href="/" />\n'
    '    <script>window.__BASE_PATH__ = "";</script>\n'
    '    <link rel="manifest" href="site.webmanifest" />\n'
    '</head>\n'
)


def test_render_index_html_noop_at_root():
    out = app_main.render_index_html(INDEX_HTML, "")
    assert '<base href="/" />' in out
    assert 'window.__BASE_PATH__ = ""' in out


def test_render_index_html_injects_subpath():
    out = app_main.render_index_html(INDEX_HTML, "/transmute")
    assert '<base href="/transmute/" />' in out
    assert 'window.__BASE_PATH__ = "/transmute"' in out
    # Relative asset references are left untouched (resolved via <base> tag).
    assert 'href="site.webmanifest"' in out
