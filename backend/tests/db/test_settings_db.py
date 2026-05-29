import pytest

from db import SettingsDB
from db.settings_db import DEFAULT_DATETIME_DISPLAY_FORMAT


@pytest.fixture
def tmp_settings_db(safe_path_test_settings, monkeypatch):
    monkeypatch.setattr(SettingsDB, "DB_PATH", ":memory:")
    db = SettingsDB()
    yield db
    db.close()


def test_get_settings_defaults_datetime_display_format(tmp_settings_db):
    settings = tmp_settings_db.get_settings("user-1")

    assert settings["datetime_display_format"] == DEFAULT_DATETIME_DISPLAY_FORMAT


def test_update_settings_persists_datetime_display_format(tmp_settings_db):
    updated = tmp_settings_db.update_settings("user-1", {"datetime_display_format": "DD/MM/YYYY - HH:mm:ss"})

    assert updated["datetime_display_format"] == "DD/MM/YYYY - HH:mm:ss"
    assert tmp_settings_db.get_settings("user-1")["datetime_display_format"] == "DD/MM/YYYY - HH:mm:ss"


def test_update_settings_rejects_invalid_datetime_display_format(tmp_settings_db):
    with pytest.raises(ValueError, match="unsupported tokens"):
        tmp_settings_db.update_settings("user-1", {"datetime_display_format": "DD/MM/YYYY test"})