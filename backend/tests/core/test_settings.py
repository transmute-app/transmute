from core.settings import Settings, get_settings


def test_settings_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    # Clear the lru_cache so a fresh Settings is constructed
    get_settings.cache_clear()
    try:
        s = Settings(data_dir=tmp_path / "data")
        assert s.app_name == "Transmute"
        assert s.port == 3313
        assert s.host == "0.0.0.0"
        assert s.auth_algorithm == "HS256"
    finally:
        get_settings.cache_clear()


def test_derived_paths_created(tmp_path):
    s = Settings(data_dir=tmp_path / "data")
    assert s.db_path == tmp_path / "data" / "db" / "app.db"
    assert s.upload_dir == tmp_path / "data" / "uploads"
    assert s.output_dir == tmp_path / "data" / "outputs"
    assert s.tmp_dir == tmp_path / "data" / "tmp"


def test_directories_are_created(tmp_path):
    s = Settings(data_dir=tmp_path / "fresh")
    assert s.upload_dir.exists()
    assert s.output_dir.exists()
    assert s.tmp_dir.exists()
    assert s.db_path.parent.exists()


def test_secret_key_auto_generated(tmp_path):
    s = Settings(data_dir=tmp_path / "data", auth_secret_key="")
    assert len(s.auth_secret_key) > 0


def test_explicit_secret_key_preserved(tmp_path):
    s = Settings(data_dir=tmp_path / "data", auth_secret_key="my-key")
    assert s.auth_secret_key == "my-key"


def test_api_server_url_default(tmp_path):
    s = Settings(data_dir=tmp_path / "data")
    assert s.api_server_url == "http://0.0.0.0:3313"


def test_api_server_url_from_app_url(tmp_path):
    s = Settings(data_dir=tmp_path / "data", app_url="https://example.com")
    assert s.api_server_url == "https://example.com"


def test_get_settings_returns_same_instance():
    get_settings.cache_clear()
    try:
        a = get_settings()
        b = get_settings()
        assert a is b
    finally:
        get_settings.cache_clear()
