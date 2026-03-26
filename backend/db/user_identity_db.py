import sqlite3
import threading
from typing import Optional

from core import get_settings, validate_sql_identifier, migrate_table_columns

'''
Anywhere you see # nosec B608, it is marking a Bandit false positive. The table
name is validated and locked after initialization, and the values are
parameterized to prevent SQL injection.
'''


class UserIdentityDB:
    """Database class for linking external OIDC identities to local users.

    Each row maps an (issuer, subject) pair from an OIDC provider to
    a local user UUID, allowing the same user to authenticate via
    multiple identity providers or via password + OIDC.

    Attributes:
        settings: Application settings instance.
        DB_PATH: Path to the SQLite database file.
        _TABLE_NAME: Name of the database table for identities.
    """

    settings = get_settings()
    DB_PATH = settings.db_path
    _TABLE_NAME = "USER_IDENTITIES"

    @property
    def TABLE_NAME(self) -> str:
        """str: The validated, immutable table name."""
        return self._table_name

    def __init__(self) -> None:
        """Initialize UserIdentityDB, validate the table name, and create tables."""
        object.__setattr__(self, '_table_name', validate_sql_identifier(self._TABLE_NAME))
        self._local = threading.local()
        self.create_tables()

    @property
    def conn(self) -> sqlite3.Connection:
        """Return a thread-local SQLite connection, creating one if needed."""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.DB_PATH)
        return self._local.conn

    def create_tables(self) -> None:
        """Create the user identities table if it does not already exist."""
        with self.conn:
            self.conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_uuid TEXT NOT NULL,
                    issuer TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)  # nosec B608

        with self.conn:
            self.conn.execute(
                f"CREATE UNIQUE INDEX IF NOT EXISTS idx_{self.TABLE_NAME.lower()}_issuer_subject "  # nosec B608
                f"ON {self.TABLE_NAME} (issuer, subject)"
            )

        with self.conn:
            self.conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{self.TABLE_NAME.lower()}_user_uuid "  # nosec B608
                f"ON {self.TABLE_NAME} (user_uuid)"
            )

        migrate_table_columns(self.conn, self.TABLE_NAME, {
            "user_uuid": "TEXT NOT NULL",
            "issuer": "TEXT NOT NULL",
            "subject": "TEXT NOT NULL",
            "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        })

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        """Normalize a raw database row into identity data."""
        return {
            "id": row["id"],
            "user_uuid": row["user_uuid"],
            "issuer": row["issuer"],
            "subject": row["subject"],
            "created_at": row["created_at"],
        }

    def get_by_issuer_subject(self, issuer: str, subject: str) -> Optional[dict]:
        """Look up a linked identity by issuer and subject."""
        cursor = self.conn.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(
            f"SELECT id, user_uuid, issuer, subject, created_at FROM {self.TABLE_NAME} "  # nosec B608
            f"WHERE issuer = ? AND subject = ?",
            (issuer, subject),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def link_identity(self, user_uuid: str, issuer: str, subject: str) -> dict:
        """Create a new identity link for a local user.

        Returns:
            The created identity row as a dictionary.

        Raises:
            sqlite3.IntegrityError: If the issuer+subject pair already exists.
        """
        with self.conn:
            cursor = self.conn.execute(
                f"INSERT INTO {self.TABLE_NAME} (user_uuid, issuer, subject) "  # nosec B608
                f"VALUES (?, ?, ?)",
                (user_uuid, issuer, subject),
            )
        return {
            "id": cursor.lastrowid,
            "user_uuid": user_uuid,
            "issuer": issuer,
            "subject": subject,
        }

    def get_identities_for_user(self, user_uuid: str) -> list[dict]:
        """Return all linked identities for a given user."""
        cursor = self.conn.cursor()
        cursor.row_factory = sqlite3.Row
        cursor.execute(
            f"SELECT id, user_uuid, issuer, subject, created_at FROM {self.TABLE_NAME} "  # nosec B608
            f"WHERE user_uuid = ?",
            (user_uuid,),
        )
        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def delete_identity(self, identity_id: int) -> bool:
        """Remove an identity link by its row ID.

        Returns:
            True if a row was deleted, False otherwise.
        """
        with self.conn:
            cursor = self.conn.execute(
                f"DELETE FROM {self.TABLE_NAME} WHERE id = ?",  # nosec B608
                (identity_id,),
            )
        return cursor.rowcount > 0
