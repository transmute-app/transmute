import pytest
from db import SettingsDB
from db.settings_db import (
    BUILTIN_THEME_KEYS,
    THEME_COLOR_TOKENS,
    Theme,
    _normalize_hex_color,
    _slugify_theme_name,
)


VALID_COLORS = {
    "primary":       "#ef4444",
    "primary_light": "#f87171",
    "primary_dark":  "#dc2626",
    "accent":        "#f59e0b",
    "success":       "#16a34a",
    "success_light": "#22c55e",
    "success_dark":  "#15803d",
    "surface_dark":  "#0f172a",
    "surface_light": "#1e293b",
    "text":          "#f8fafc",
    "text_muted":    "#94a3b8",
}


@pytest.fixture
def tmp_settings_db(safe_path_test_settings, monkeypatch):
    monkeypatch.setattr(SettingsDB, "DB_PATH", ":memory:")
    db = SettingsDB()
    yield db
    db.close()


# ===== Helper-level tests =====


def test_normalize_hex_short_form_expands():
    assert _normalize_hex_color("#fff") == "#ffffff"
    assert _normalize_hex_color("#A1B") == "#aa11bb"


def test_normalize_hex_rejects_invalid():
    with pytest.raises(ValueError):
        _normalize_hex_color("not-a-color")
    with pytest.raises(ValueError):
        _normalize_hex_color("#12345")  # 5 digits
    with pytest.raises(ValueError):
        _normalize_hex_color("ef4444")  # missing #


def test_slugify_falls_back_on_unicode():
    assert _slugify_theme_name("Midnight Forest") == "midnight-forest"
    assert _slugify_theme_name("夜の森").startswith("custom-")


# ===== CRUD tests =====


def test_list_custom_themes_starts_empty(tmp_settings_db):
    assert tmp_settings_db.list_custom_themes() == []


def test_create_custom_theme_persists_and_normalizes(tmp_settings_db):
    theme = tmp_settings_db.create_custom_theme("Midnight Forest", VALID_COLORS)
    assert theme["key"] == "midnight-forest"
    assert theme["name"] == "Midnight Forest"
    for tok in THEME_COLOR_TOKENS:
        assert theme["colors"][tok] == VALID_COLORS[tok].lower()


def test_create_rejects_missing_color_token(tmp_settings_db):
    incomplete = {k: v for k, v in VALID_COLORS.items() if k != "accent"}
    with pytest.raises(ValueError, match="Missing required color tokens"):
        tmp_settings_db.create_custom_theme("Bad", incomplete)


def test_create_rejects_invalid_hex(tmp_settings_db):
    bad = {**VALID_COLORS, "primary": "blue"}
    with pytest.raises(ValueError, match="Invalid color"):
        tmp_settings_db.create_custom_theme("Bad", bad)


def test_create_rejects_empty_name(tmp_settings_db):
    with pytest.raises(ValueError, match="non-empty"):
        tmp_settings_db.create_custom_theme("   ", VALID_COLORS)


def test_create_rejects_duplicate_name_case_insensitive(tmp_settings_db):
    tmp_settings_db.create_custom_theme("Oceanic", VALID_COLORS)
    with pytest.raises(ValueError, match="already exists"):
        tmp_settings_db.create_custom_theme("oceanic", VALID_COLORS)


def test_create_generates_unique_key_when_slug_collides(tmp_settings_db):
    # Force a slug collision by creating a theme whose slug matches a built-in.
    # `_slugify_theme_name("Rubedo")` would produce "rubedo" which is reserved
    # — the helper should auto-suffix.
    theme = tmp_settings_db.create_custom_theme("Rubedo!", VALID_COLORS)
    assert theme["key"] not in BUILTIN_THEME_KEYS
    assert theme["key"].startswith("rubedo")


def test_get_custom_theme_returns_none_for_missing(tmp_settings_db):
    assert tmp_settings_db.get_custom_theme("nope") is None


def test_update_custom_theme_changes_name_and_colors(tmp_settings_db):
    created = tmp_settings_db.create_custom_theme("First", VALID_COLORS)
    key = created["key"]
    new_colors = {**VALID_COLORS, "primary": "#123456"}
    updated = tmp_settings_db.update_custom_theme(key, name="Renamed", colors=new_colors)
    assert updated["key"] == key  # key never changes
    assert updated["name"] == "Renamed"
    assert updated["colors"]["primary"] == "#123456"


def test_update_rejects_duplicate_name(tmp_settings_db):
    tmp_settings_db.create_custom_theme("Alpha", VALID_COLORS)
    beta = tmp_settings_db.create_custom_theme("Beta", VALID_COLORS)
    with pytest.raises(ValueError, match="already exists"):
        tmp_settings_db.update_custom_theme(beta["key"], name="Alpha")


def test_update_unknown_theme_raises(tmp_settings_db):
    with pytest.raises(ValueError, match="does not exist"):
        tmp_settings_db.update_custom_theme("ghost", name="Nope")


def test_delete_custom_theme_resets_users_to_rubedo(tmp_settings_db):
    created = tmp_settings_db.create_custom_theme("Doomed", VALID_COLORS)
    key = created["key"]
    # Bypass admin scoping by inserting a settings row directly.
    user_id = "user-1"
    tmp_settings_db.conn.execute(
        f"INSERT INTO {tmp_settings_db.TABLE_NAME} (user_id, theme, auto_download, keep_originals, cleanup_enabled, cleanup_ttl_minutes) "
        f"VALUES (?, ?, 0, 1, 1, 60)",
        (user_id, key),
    )
    tmp_settings_db.conn.commit()

    assert tmp_settings_db.delete_custom_theme(key) is True
    assert tmp_settings_db.get_custom_theme(key) is None

    row = tmp_settings_db.conn.execute(
        f"SELECT theme FROM {tmp_settings_db.TABLE_NAME} WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    assert row[0] == Theme.RUBEDO.value


def test_delete_missing_theme_returns_false(tmp_settings_db):
    assert tmp_settings_db.delete_custom_theme("ghost") is False


# ===== Settings.update_settings theme validation =====


def test_update_settings_accepts_builtin_theme(tmp_settings_db):
    tmp_settings_db.update_settings("u1", {"theme": "viriditas"})
    assert tmp_settings_db.get_settings("u1")["theme"] == "viriditas"


def test_update_settings_accepts_custom_theme(tmp_settings_db):
    created = tmp_settings_db.create_custom_theme("Custom One", VALID_COLORS)
    tmp_settings_db.update_settings("u1", {"theme": created["key"]})
    assert tmp_settings_db.get_settings("u1")["theme"] == created["key"]


def test_update_settings_rejects_unknown_theme(tmp_settings_db):
    with pytest.raises(ValueError, match="Invalid theme"):
        tmp_settings_db.update_settings("u1", {"theme": "not-a-theme"})


def test_update_settings_rejects_non_string_theme(tmp_settings_db):
    with pytest.raises(ValueError, match="non-empty string"):
        tmp_settings_db.update_settings("u1", {"theme": 42})
