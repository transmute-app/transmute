import sqlite3
import threading
from enum import Enum
from typing import Optional

from core import get_settings, migrate_table_columns, validate_sql_identifier

'''
Anywhere you see # nosec B608, it is marking a Bandit false positive. The table
name is validated and locked after initialization, and the values are
parameterized to prevent SQL injection.
'''


class UserRole(str, Enum):
    """Enumeration of available application roles."""

    ADMIN = "admin"
    MEMBER = "member"


class UserDB:
    """Database class for managing application users.

    Stores user account records including credentials, role information,
    and whether the account is disabled.

    Attributes:
        settings: Application settings instance.
        DB_PATH: Path to the SQLite database file.
        _TABLE_NAME: Name of the database table for users.
        conn: Active SQLite database connection.
    """

    settings = get_settings()
    DB_PATH = settings.db_path
    _TABLE_NAME = settings.user_table_name

    @property
    def TABLE_NAME(self) -> str:
        """str: The validated, immutable table name."""
        return self._table_name

    def __init__(self) -> None:
        """Initialize UserDB, validate the table name, and create tables."""
        object.__setattr__(self, '_table_name', validate_sql_identifier(self._TABLE_NAME))
        self._local = threading.local()
        self.create_tables()

    @property
    def conn(self) -> sqlite3.Connection:
        """Return a thread-local SQLite connection, creating one if needed."""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.DB_PATH)
        return self._local.conn

    @staticmethod
    def _normalize_role(role: str | UserRole) -> str:
        """Validate and normalize a role value for storage."""
        return UserRole(role).value

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        """Normalize a raw database row into typed user data."""
        return {
            "uuid": row["uuid"],
            "username": row["username"],
            "email": row["email"],
            "full_name": row["full_name"],
            "hashed_password": row["hashed_password"],
            "role": row["role"],
            "disabled": bool(row["disabled"]),
        }

    def create_tables(self) -> None:
        """Create the users table if it does not already exist."""
        with self.conn:
            self.conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
                    uuid TEXT PRIMARY KEY UNIQUE,
                    username TEXT NOT NULL,
                    email TEXT,
                    full_name TEXT,
                    hashed_password TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT '{UserRole.MEMBER.value}',
                    disabled INTEGER NOT NULL DEFAULT 0
                )
            """)  # nosec B608

        with self.conn:
            self.conn.execute(
                f"CREATE UNIQUE INDEX IF NOT EXISTS idx_{self.TABLE_NAME.lower()}_username_unique ON {self.TABLE_NAME} (username)"  # nosec B608
            )

        migrate_table_columns(self.conn, self.TABLE_NAME, {
            "username": "TEXT",
            "email": "TEXT",
            "full_name": "TEXT",
            "hashed_password": "TEXT",  # nosec B105, false positive hardcoded password: 'TEXT'
            "role": f"TEXT NOT NULL DEFAULT '{UserRole.MEMBER.value}'",
            "disabled": "INTEGER NOT NULL DEFAULT 0",
        })

    def insert_user(self, user_data: dict) -> dict:
        """Insert a new user record into the database.

        Args:
            user_data: A dictionary containing the following required keys:
                uuid (str): Stable unique identifier for the user.
                username (str): Username for the account.
                email (str | None): Optional email address.
                full_name (str | None): Optional display name.
                hashed_password (str): Password hash for the account.
                role (str | UserRole): Role assigned to the user.
                disabled (bool): Whether the account is disabled.

        Returns:
            The inserted user record as a normalized dictionary.

        Raises:
            ValueError: If user_data contains missing or extra fields, or an
                invalid role value.
        """
        required_fields = {
            "uuid",
            "username",
            "email",
            "full_name",
            "hashed_password",
            "role",
            "disabled",
        }
        if set(user_data.keys()) != required_fields:
            diff = required_fields.symmetric_difference(user_data.keys())
            raise ValueError(
                "User data must contain the following fields: "
                f"{sorted(required_fields)}. Missing or extra fields: {diff}"
            )

        normalized_user = {
            "uuid": user_data["uuid"],
            "username": user_data["username"],
            "email": user_data["email"],
            "full_name": user_data["full_name"],
            "hashed_password": user_data["hashed_password"],
            "role": self._normalize_role(user_data["role"]),
            "disabled": int(bool(user_data["disabled"])),
        }

        with self.conn:
            self.conn.execute(
                f"INSERT INTO {self.TABLE_NAME} (uuid, username, email, full_name, hashed_password, role, disabled) "  # nosec B608
                f"VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    normalized_user["uuid"],
                    normalized_user["username"],
                    normalized_user["email"],
                    normalized_user["full_name"],
                    normalized_user["hashed_password"],
                    normalized_user["role"],
                    normalized_user["disabled"],
                )
            )

        normalized_user["disabled"] = bool(normalized_user["disabled"])
        return normalized_user

    def get_user(self, user_uuid: str) -> Optional[dict]:
        """Retrieve a user by UUID."""
        cursor = self.conn.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(
            f"SELECT uuid, username, email, full_name, hashed_password, role, disabled FROM {self.TABLE_NAME} WHERE uuid = ?",  # nosec B608
            (user_uuid,)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def get_user_by_username(self, username: str) -> Optional[dict]:
        """Retrieve the first matching user by username."""
        cursor = self.conn.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(
            f"SELECT uuid, username, email, full_name, hashed_password, role, disabled FROM {self.TABLE_NAME} WHERE username = ?",  # nosec B608
            (username,)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def get_user_by_email(self, email: str) -> Optional[dict]:
        """Retrieve the first matching user by email."""
        cursor = self.conn.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(
            f"SELECT uuid, username, email, full_name, hashed_password, role, disabled FROM {self.TABLE_NAME} WHERE email = ?",  # nosec B608
            (email,)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def username_exists(self, username: str, exclude_uuid: str | None = None) -> bool:
        """Return whether a username is already used by another account."""
        cursor = self.conn.cursor()
        if exclude_uuid is None:
            cursor.execute(
                f"SELECT 1 FROM {self.TABLE_NAME} WHERE username = ? LIMIT 1",  # nosec B608
                (username,)
            )
        else:
            cursor.execute(
                f"SELECT 1 FROM {self.TABLE_NAME} WHERE username = ? AND uuid != ? LIMIT 1",  # nosec B608
                (username, exclude_uuid)
            )
        return cursor.fetchone() is not None

    def count_users(self) -> int:
        """Return the total number of users in the database."""
        cursor = self.conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {self.TABLE_NAME}")  # nosec B608
        row = cursor.fetchone()
        return int(row[0]) if row is not None else 0

    def has_users(self) -> bool:
        """Return whether at least one user exists."""
        return self.count_users() > 0

    def list_users(self) -> list[dict]:
        """Retrieve all users from the database."""
        cursor = self.conn.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(
            f"SELECT uuid, username, email, full_name, hashed_password, role, disabled FROM {self.TABLE_NAME} ORDER BY username",  # nosec B608
        )
        rows = cursor.fetchall()
        return [self._row_to_dict(row) for row in rows]

    def update_user(self, user_uuid: str, updates: dict) -> Optional[dict]:
        """Apply a partial update to an existing user.

        The UUID is immutable and cannot be updated.
        """
        allowed = {"username", "email", "full_name", "hashed_password", "role", "disabled"}
        filtered = {key: value for key, value in updates.items() if key in allowed}

        if not filtered:
            return self.get_user(user_uuid)

        if "role" in filtered:
            filtered["role"] = self._normalize_role(filtered["role"])
        if "disabled" in filtered:
            filtered["disabled"] = int(bool(filtered["disabled"]))

        set_clause = ", ".join(f"{column} = ?" for column in filtered)
        values = list(filtered.values()) + [user_uuid]

        with self.conn:
            cursor = self.conn.execute(
                f"UPDATE {self.TABLE_NAME} SET {set_clause} WHERE uuid = ?",  # nosec B608
                values
            )

        if cursor.rowcount == 0:
            return None
        return self.get_user(user_uuid)

    def delete_user(self, user_uuid: str) -> bool:
        """Delete a user by UUID."""
        with self.conn:
            cursor = self.conn.execute(
                f"DELETE FROM {self.TABLE_NAME} WHERE uuid = ?",  # nosec B608
                (user_uuid,)
            )
        return cursor.rowcount > 0

    def close(self) -> None:
        """Close the current thread's database connection."""
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
