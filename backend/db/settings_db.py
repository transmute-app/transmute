import sqlite3
from enum import Enum
from core import get_settings, validate_sql_identifier

'''
Anywhere you see # nosec B608, it is marking a Bandit false positive. The table 
name is validated and locked after initialization, and the values are 
parameterized to prevent SQL injection.
'''


class Theme(str, Enum):
    RUBEDO     = "rubedo"
    CITRINITAS = "citrinitas"
    VIRIDITAS  = "viriditas"
    NIGREDO    = "nigredo"
    ALBEDO     = "albedo"


# Defaults applied on first run / if the row is missing
_DEFAULT_SETTINGS = {
    "theme":            Theme.RUBEDO.value,
    "auto_download":    False,
    "keep_originals":   True,
}

_SETTINGS_ROW_ID = 1  # Single-row table; always read/write row with this id


class SettingsDB:
    settings = get_settings()
    DB_PATH = settings.db_path
    _TABLE_NAME = settings.app_settings_table_name

    @property
    def TABLE_NAME(self) -> str:
        return self._table_name

    def __init__(self):
        # Validate and lock table name — immutable after init
        object.__setattr__(self, '_table_name', validate_sql_identifier(self._TABLE_NAME))
        self.conn = sqlite3.connect(self.DB_PATH, check_same_thread=False)
        self.create_tables()
        self._seed_defaults()

    def create_tables(self):
        with self.conn:
            self.conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
                    id             INTEGER PRIMARY KEY,
                    theme          TEXT    NOT NULL DEFAULT '{Theme.RUBEDO.value}',
                    auto_download  INTEGER NOT NULL DEFAULT 0,
                    keep_originals INTEGER NOT NULL DEFAULT 1
                )
            """)  # nosec B608

    def _seed_defaults(self):
        """Insert the default row if it does not already exist."""
        cursor = self.conn.cursor()
        cursor.execute(
            f"SELECT id FROM {self.TABLE_NAME} WHERE id = ?",  # nosec B608
            (_SETTINGS_ROW_ID,)
        )
        if cursor.fetchone() is None:
            with self.conn:
                self.conn.execute(
                    f"INSERT INTO {self.TABLE_NAME} (id, theme, auto_download, keep_originals) "  # nosec B608
                    f"VALUES (?, ?, ?, ?)",
                    (
                        _SETTINGS_ROW_ID,
                        _DEFAULT_SETTINGS["theme"],
                        int(_DEFAULT_SETTINGS["auto_download"]),
                        int(_DEFAULT_SETTINGS["keep_originals"]),
                    )
                )

    def _row_to_dict(self, row: tuple) -> dict:
        return {
            "theme":          row[1],
            "auto_download":  bool(row[2]),
            "keep_originals": bool(row[3]),
        }

    def get_settings(self) -> dict:
        """Return the current app settings as a dict."""
        cursor = self.conn.cursor()
        cursor.execute(
            f"SELECT * FROM {self.TABLE_NAME} WHERE id = ?",  # nosec B608
            (_SETTINGS_ROW_ID,)
        )
        row = cursor.fetchone()
        if row is None:
            return dict(_DEFAULT_SETTINGS)
        return self._row_to_dict(row)

    def update_settings(self, updates: dict) -> dict:
        """
        Apply a partial or full update to app settings.

        Accepted keys: theme, auto_download, keep_originals.
        Unknown keys are silently ignored.
        Raises ValueError for invalid theme values.
        Returns the updated settings dict.
        """
        # Prevent SQL injection by allowing only known columns
        allowed = {"theme", "auto_download", "keep_originals"}
        filtered = {k: v for k, v in updates.items() if k in allowed}

        if not filtered:
            return self.get_settings()

        # Prevent SQL injection by allowing only known theme values
        if "theme" in filtered:
            try:
                filtered["theme"] = Theme(filtered["theme"]).value
            except ValueError:
                valid = [t.value for t in Theme]
                raise ValueError(
                    f"Invalid theme '{filtered['theme']}'. Valid options: {valid}"
                )

        set_clause = ", ".join(f"{col} = ?" for col in filtered)
        values = list(filtered.values())

        # Coerce booleans to ints for SQLite storage
        # Prevent SQL injection by allowing only integers for these
        for i, key in enumerate(filtered):
            if key in ("auto_download", "keep_originals"):
                values[i] = int(values[i])

        with self.conn:
            self.conn.execute(  # nosec B608
                f"UPDATE {self.TABLE_NAME} SET {set_clause} WHERE id = ?",
                [*values, _SETTINGS_ROW_ID]
            )

        return self.get_settings()

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
