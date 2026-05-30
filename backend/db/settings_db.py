import re
import sqlite3
import threading
from datetime import datetime, timezone
from enum import Enum
from core import get_settings, validate_sql_identifier, migrate_table_columns, assign_orphaned_rows_to_admin

'''
Anywhere you see # nosec B608, it is marking a Bandit false positive. The table 
name is validated and locked after initialization, and the values are 
parameterized to prevent SQL injection.
'''


class Theme(str, Enum):
    """Enumeration of available built-in UI themes.

    Custom user-defined themes are stored in the CUSTOM_THEMES table and
    validated at runtime; this enum only enumerates the themes that ship
    with the app and whose CSS variables live in frontend/src/index.css.
    """

    RUBEDO     = "rubedo"
    CITRINITAS = "citrinitas"
    VIRIDITAS  = "viriditas"
    NIGREDO    = "nigredo"
    ALBEDO     = "albedo"
    AURORA     = "aurora"
    CAELUM     = "caelum"
    ARGENTUM   = "argentum"
    CATPPUCCIN_MOCHA = "catppuccin_mocha"
    CATPPUCCIN_MACCHIATO = "catppuccin_macchiato"
    CATPPUCCIN_FRAPPE = "catppuccin_frappe"
    CATPPUCCIN_LATTE = "catppuccin_latte"


# Color tokens every theme (built-in or custom) must define. Order matters
# only for stable serialization in API responses.
THEME_COLOR_TOKENS: tuple[str, ...] = (
    "primary",
    "primary_light",
    "primary_dark",
    "accent",
    "success",
    "success_light",
    "success_dark",
    "surface_dark",
    "surface_light",
    "text",
    "text_muted",
)


# Slug rules: lowercase, digits, dashes; must start with a letter.
_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]*$")
# Accept #RGB or #RRGGBB
_HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

# Reserve a name prefix to prevent collisions with built-ins, even if a
# new built-in is added later.
BUILTIN_THEME_KEYS: frozenset[str] = frozenset(t.value for t in Theme)


def _normalize_hex_color(value: str) -> str:
    """Normalize a hex color to lowercase 7-character form (#rrggbb)."""
    if not isinstance(value, str) or not _HEX_COLOR_RE.match(value):
        raise ValueError(f"Invalid hex color: {value!r}")
    v = value.lower()
    if len(v) == 4:
        # Expand #rgb to #rrggbb
        v = "#" + "".join(ch * 2 for ch in v[1:])
    return v


def _slugify_theme_name(name: str) -> str:
    """Convert a display name to a stable URL-safe key."""
    if not isinstance(name, str):
        raise ValueError("Theme name must be a string")
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    if not slug or not slug[0].isalpha():
        slug = "custom-" + (slug or "theme")
    return slug


# Defaults applied when a user has no settings row yet
_DEFAULT_SETTINGS = {
    "theme":            Theme.RUBEDO.value,
    "auto_download":    False,
    "keep_originals":   True,
    "cleanup_enabled":  True,
    "cleanup_ttl_minutes": 60
}


class SettingsDB:
    """Database class for managing application settings.

    Manages a single-row settings table that stores user-configurable
    application preferences such as theme, auto-download behaviour,
    and whether original files are retained after conversion.

    Attributes:
        settings: Application settings instance.
        DB_PATH: Path to the SQLite database file.
        _TABLE_NAME: Name of the database table for app settings.
        conn: Active SQLite database connection.
    """

    settings = get_settings()
    DB_PATH = settings.db_path
    _TABLE_NAME = settings.app_settings_table_name
    _CUSTOM_THEMES_TABLE_NAME = settings.custom_themes_table_name

    @property
    def TABLE_NAME(self) -> str:
        """str: The validated, immutable table name."""
        return self._table_name

    @property
    def CUSTOM_THEMES_TABLE_NAME(self) -> str:
        """str: The validated, immutable custom themes table name."""
        return self._custom_themes_table_name

    def __init__(self) -> None:
        """Initialize SettingsDB, validate the table name, and create tables."""
        # Validate and lock table name — immutable after init
        object.__setattr__(self, '_table_name', validate_sql_identifier(self._TABLE_NAME))
        object.__setattr__(
            self,
            '_custom_themes_table_name',
            validate_sql_identifier(self._CUSTOM_THEMES_TABLE_NAME),
        )
        self._local = threading.local()
        self.create_tables()

    @property
    def conn(self) -> sqlite3.Connection:
        """Return a thread-local SQLite connection, creating one if needed."""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.DB_PATH)
        return self._local.conn

    def create_tables(self) -> None:
        """Create the app settings table if it does not already exist."""
        with self.conn:
            self.conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
                    id             INTEGER PRIMARY KEY,
                    user_id        TEXT,
                    theme          TEXT    NOT NULL DEFAULT '{Theme.RUBEDO.value}',
                    auto_download  INTEGER NOT NULL DEFAULT 0,
                    keep_originals INTEGER NOT NULL DEFAULT 1,
                    cleanup_enabled INTEGER NOT NULL DEFAULT 1,
                    cleanup_ttl_minutes INTEGER NOT NULL DEFAULT 60
                )
            """)  # nosec B608

        # Ensure every expected column exists (handles older DB schemas)
        migrate_table_columns(self.conn, self.TABLE_NAME, {
            "user_id":             "TEXT",
            "theme":               f"TEXT NOT NULL DEFAULT '{Theme.RUBEDO.value}'",
            "auto_download":       "INTEGER NOT NULL DEFAULT 0",
            "keep_originals":      "INTEGER NOT NULL DEFAULT 1",
            "cleanup_enabled":     "INTEGER NOT NULL DEFAULT 1",
            "cleanup_ttl_minutes": "INTEGER NOT NULL DEFAULT 60",
        })  # nosec B608

        # Assign pre-auth orphaned rows to the first admin
        assign_orphaned_rows_to_admin(self.conn, self.TABLE_NAME)

        # Custom themes table (admin-managed, shared across all users).
        # NOTE: several token names (`primary`, `text`, `accent`) collide with
        # SQLite reserved words / type names, so every color column is quoted
        # in DDL and DML using double quotes.
        color_columns_sql = ",\n                    ".join(
            f'"{tok}" TEXT NOT NULL' for tok in THEME_COLOR_TOKENS
        )
        with self.conn:
            self.conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.CUSTOM_THEMES_TABLE_NAME} (
                    id         INTEGER PRIMARY KEY,
                    key        TEXT NOT NULL UNIQUE,
                    name       TEXT NOT NULL,
                    {color_columns_sql},
                    created_by TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)  # nosec B608

    def _ensure_user_row(self, user_id: str) -> None:
        """Insert the default settings row for a user if it does not already exist."""
        cursor = self.conn.cursor()
        cursor.execute(
            f"SELECT id FROM {self.TABLE_NAME} WHERE user_id = ?",  # nosec B608
            (user_id,)
        )
        if cursor.fetchone() is None:
            with self.conn:
                self.conn.execute(
                    f"INSERT INTO {self.TABLE_NAME} (user_id, theme, auto_download, keep_originals, cleanup_enabled, cleanup_ttl_minutes) "  # nosec B608
                    f"VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        user_id,
                        _DEFAULT_SETTINGS["theme"],
                        int(_DEFAULT_SETTINGS["auto_download"]),
                        int(_DEFAULT_SETTINGS["keep_originals"]),
                        int(_DEFAULT_SETTINGS["cleanup_enabled"]),
                        int(_DEFAULT_SETTINGS["cleanup_ttl_minutes"]),
                    )
                )

    @staticmethod
    def _row_to_dict(row: dict) -> dict:
        """Normalise a raw database row dict into typed application settings.

        Args:
            row: A dictionary produced by the Row-factory cursor, keyed by
                column name.

        Returns:
            A dictionary with keys theme (str), auto_download (bool),
            keep_originals (bool), cleanup_enabled (bool), and
            cleanup_ttl_minutes (int).
        """
        return {
            "theme":               row["theme"],
            "auto_download":       bool(row["auto_download"]),
            "keep_originals":      bool(row["keep_originals"]),
            "cleanup_enabled":     bool(row["cleanup_enabled"]),
            "cleanup_ttl_minutes": int(row["cleanup_ttl_minutes"]),
        }

    def get_settings(self, user_id: str) -> dict:
        """Return the settings for a given user, creating defaults if needed."""
        self._ensure_user_row(user_id)
        cursor = self.conn.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(
            f"SELECT * FROM {self.TABLE_NAME} WHERE user_id = ?",  # nosec B608
            (user_id,)
        )
        row = cursor.fetchone()
        if row is None:
            return dict(_DEFAULT_SETTINGS)
        return self._row_to_dict(row)

    def update_settings(self, user_id: str, updates: dict) -> dict:
        """Apply a partial or full update to a user's settings."""
        self._ensure_user_row(user_id)
        # Prevent SQL injection by allowing only known columns
        allowed = {"theme", "auto_download", "keep_originals", "cleanup_enabled", "cleanup_ttl_minutes"}
        filtered = {k: v for k, v in updates.items() if k in allowed}

        if not filtered:
            return self.get_settings(user_id)

        # Validate theme value against built-ins and the custom themes table.
        # Custom themes are admin-managed but every user may *select* them.
        if "theme" in filtered:
            theme_value = filtered["theme"]
            if not isinstance(theme_value, str) or not theme_value:
                raise ValueError("Theme must be a non-empty string")
            if theme_value not in BUILTIN_THEME_KEYS and not self._custom_theme_exists(theme_value):
                valid_builtins = sorted(BUILTIN_THEME_KEYS)
                raise ValueError(
                    f"Invalid theme '{theme_value}'. Must be a built-in "
                    f"({valid_builtins}) or an existing custom theme key."
                )
            filtered["theme"] = theme_value

        if "auto_download" in filtered:
            filtered["auto_download"] = int(bool(filtered["auto_download"]))
        if "keep_originals" in filtered:
            filtered["keep_originals"] = int(bool(filtered["keep_originals"]))
        if "cleanup_enabled" in filtered:
            filtered["cleanup_enabled"] = int(bool(filtered["cleanup_enabled"]))
        if "cleanup_ttl_minutes" in filtered:
            filtered["cleanup_ttl_minutes"] = int(filtered["cleanup_ttl_minutes"])

        set_clause = ", ".join(f"{col} = ?" for col in filtered)
        values = list(filtered.values()) + [user_id]

        with self.conn:
            self.conn.execute(
                f"UPDATE {self.TABLE_NAME} SET {set_clause} WHERE user_id = ?",  # nosec B608
                values
            )

        return self.get_settings(user_id)

    def get_admin_cleanup_settings(self) -> dict:
        """Return cleanup settings from the first admin user's row.

        Falls back to defaults if no admin settings row exists or the
        users table has not been created yet (fresh install).
        Used by the background cleanup task.
        """
        try:
            cursor = self.conn.cursor()
            cursor.row_factory = sqlite3.Row
            # Find the first admin's settings by joining against the users table
            user_table = validate_sql_identifier(self.settings.user_table_name)
            cursor.execute(
                f"SELECT s.cleanup_enabled, s.cleanup_ttl_minutes "
                f"FROM {self.TABLE_NAME} s "
                f"INNER JOIN {user_table} u ON s.user_id = u.uuid "
                f"WHERE u.role = 'admin' "
                f"ORDER BY u.rowid LIMIT 1",  # nosec B608
            )
            row = cursor.fetchone()
        except sqlite3.OperationalError:
            row = None
        if row is None:
            return {
                "cleanup_enabled": _DEFAULT_SETTINGS["cleanup_enabled"],
                "cleanup_ttl_minutes": _DEFAULT_SETTINGS["cleanup_ttl_minutes"],
            }
        return {
            "cleanup_enabled": bool(row["cleanup_enabled"]),
            "cleanup_ttl_minutes": int(row["cleanup_ttl_minutes"]),
        }

    def delete_settings(self, user_id: str) -> bool:
        """Delete the settings row for a given user. Returns True if a row was deleted."""
        with self.conn:
            cursor = self.conn.execute(
                f"DELETE FROM {self.TABLE_NAME} WHERE user_id = ?",  # nosec B608
                (user_id,)
            )
        return cursor.rowcount > 0

    # ===== Custom theme management =====

    @staticmethod
    def _validate_color_payload(colors: dict) -> dict[str, str]:
        """Normalize and validate the required color token payload.

        Args:
            colors: A mapping of token name to hex color string.

        Returns:
            A dict containing every token in THEME_COLOR_TOKENS with values
            normalized to lowercase 7-character hex.

        Raises:
            ValueError: If any token is missing or any value is not a valid hex color.
        """
        if not isinstance(colors, dict):
            raise ValueError("Theme colors payload must be an object")
        missing = [tok for tok in THEME_COLOR_TOKENS if tok not in colors or colors[tok] in (None, "")]
        if missing:
            raise ValueError(f"Missing required color tokens: {missing}")
        normalized: dict[str, str] = {}
        for tok in THEME_COLOR_TOKENS:
            try:
                normalized[tok] = _normalize_hex_color(colors[tok])
            except ValueError as exc:
                raise ValueError(f"Invalid color for '{tok}': {colors[tok]!r}") from exc
        return normalized

    def _custom_theme_exists(self, key: str) -> bool:
        cursor = self.conn.execute(
            f"SELECT 1 FROM {self.CUSTOM_THEMES_TABLE_NAME} WHERE key = ? LIMIT 1",  # nosec B608
            (key,),
        )
        return cursor.fetchone() is not None

    @staticmethod
    def _custom_theme_row_to_dict(row: sqlite3.Row) -> dict:
        colors = {tok: row[tok] for tok in THEME_COLOR_TOKENS}
        return {
            "key": row["key"],
            "name": row["name"],
            "colors": colors,
            "created_by": row["created_by"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def list_custom_themes(self) -> list[dict]:
        """Return every custom theme ordered by display name (case-insensitive)."""
        cursor = self.conn.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(
            f"SELECT * FROM {self.CUSTOM_THEMES_TABLE_NAME} ORDER BY LOWER(name)"  # nosec B608
        )
        return [self._custom_theme_row_to_dict(r) for r in cursor.fetchall()]

    def get_custom_theme(self, key: str) -> dict | None:
        """Return the custom theme matching key, or None if missing."""
        cursor = self.conn.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(
            f"SELECT * FROM {self.CUSTOM_THEMES_TABLE_NAME} WHERE key = ?",  # nosec B608
            (key,),
        )
        row = cursor.fetchone()
        return self._custom_theme_row_to_dict(row) if row else None

    def _generate_unique_key(self, base_slug: str) -> str:
        """Return base_slug or a suffixed variant that does not collide.

        Collisions are checked against both built-ins and existing custom theme keys.
        """
        slug = base_slug
        attempt = 2
        while slug in BUILTIN_THEME_KEYS or self._custom_theme_exists(slug):
            slug = f"{base_slug}-{attempt}"
            attempt += 1
            if attempt > 1000:  # pragma: no cover - sanity bound
                raise ValueError("Could not generate a unique theme key")
        return slug

    def create_custom_theme(
        self,
        name: str,
        colors: dict,
        created_by: str | None = None,
    ) -> dict:
        """Create a new custom theme. Display name must be non-empty and unique (case-insensitive).

        Args:
            name: Display name shown in the UI.
            colors: Mapping of every THEME_COLOR_TOKENS entry to a hex color.
            created_by: Optional user UUID of the creator.

        Returns:
            The created theme dict.

        Raises:
            ValueError: If the name is empty/duplicate or the color payload is invalid.
        """
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Theme name must be a non-empty string")
        display_name = name.strip()
        # Validate slug regex compatibility implicitly via the regex check below.
        base_slug = _slugify_theme_name(display_name)
        if not _SLUG_RE.match(base_slug):
            raise ValueError(f"Could not derive a valid theme key from '{display_name}'")

        # Reject duplicate display names case-insensitively
        cursor = self.conn.execute(
            f"SELECT 1 FROM {self.CUSTOM_THEMES_TABLE_NAME} WHERE LOWER(name) = ? LIMIT 1",  # nosec B608
            (display_name.lower(),),
        )
        if cursor.fetchone() is not None:
            raise ValueError(f"A custom theme named '{display_name}' already exists")

        normalized_colors = self._validate_color_payload(colors)
        unique_key = self._generate_unique_key(base_slug)
        now = datetime.now(timezone.utc).isoformat()

        columns = ["key", "name", *THEME_COLOR_TOKENS, "created_by", "created_at", "updated_at"]
        quoted_columns = [f'"{c}"' for c in columns]
        placeholders = ", ".join("?" for _ in columns)
        values = [
            unique_key,
            display_name,
            *(normalized_colors[tok] for tok in THEME_COLOR_TOKENS),
            created_by,
            now,
            now,
        ]
        with self.conn:
            self.conn.execute(
                f"INSERT INTO {self.CUSTOM_THEMES_TABLE_NAME} ({', '.join(quoted_columns)}) "  # nosec B608
                f"VALUES ({placeholders})",
                values,
            )
        return self.get_custom_theme(unique_key)  # type: ignore[return-value]

    def update_custom_theme(
        self,
        key: str,
        name: str | None = None,
        colors: dict | None = None,
    ) -> dict:
        """Update an existing custom theme's display name and/or colors.

        The stable `key` is never reassigned even if the display name changes.

        Raises:
            ValueError: If the theme does not exist, the new name collides,
                or color values are invalid.
        """
        existing = self.get_custom_theme(key)
        if existing is None:
            raise ValueError(f"Custom theme '{key}' does not exist")

        updates: dict[str, str] = {}

        if name is not None:
            if not isinstance(name, str) or not name.strip():
                raise ValueError("Theme name must be a non-empty string")
            new_name = name.strip()
            if new_name.lower() != existing["name"].lower():
                cursor = self.conn.execute(
                    f"SELECT 1 FROM {self.CUSTOM_THEMES_TABLE_NAME} "  # nosec B608
                    f"WHERE LOWER(name) = ? AND key != ? LIMIT 1",
                    (new_name.lower(), key),
                )
                if cursor.fetchone() is not None:
                    raise ValueError(f"A custom theme named '{new_name}' already exists")
            updates["name"] = new_name

        if colors is not None:
            normalized = self._validate_color_payload(colors)
            updates.update(normalized)

        if not updates:
            return existing

        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        set_clause = ", ".join(f'"{col}" = ?' for col in updates)
        values = list(updates.values()) + [key]
        with self.conn:
            self.conn.execute(
                f"UPDATE {self.CUSTOM_THEMES_TABLE_NAME} SET {set_clause} WHERE key = ?",  # nosec B608
                values,
            )
        return self.get_custom_theme(key)  # type: ignore[return-value]

    def delete_custom_theme(self, key: str) -> bool:
        """Delete a custom theme and reset any users currently selecting it to rubedo.

        Returns True if the theme existed and was deleted.
        """
        if not self._custom_theme_exists(key):
            return False
        fallback = Theme.RUBEDO.value
        with self.conn:
            # Reset users whose active selection is the theme being deleted.
            self.conn.execute(
                f"UPDATE {self.TABLE_NAME} SET theme = ? WHERE theme = ?",  # nosec B608
                (fallback, key),
            )
            cursor = self.conn.execute(
                f"DELETE FROM {self.CUSTOM_THEMES_TABLE_NAME} WHERE key = ?",  # nosec B608
                (key,),
            )
        return cursor.rowcount > 0

    def close(self) -> None:
        """Close the current thread's database connection."""
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
