from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration.

    Values are loaded from:
    1. Environment variables
    2. .env file (if present)
    3. Defaults defined here
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ===== Core =====

    app_name: str = "Transmute"
    app_version: str = "0.0.1"

    # ===== Storage =====

    data_dir: Path = Field(default=Path("data"))
    web_dir: Path = Field(default=Path("frontend/dist"))

    # Derived paths (computed automatically)
    db_path: Path | None = None
    upload_dir: Path | None = None
    output_dir: Path | None = None
    tmp_dir: Path | None = None

    # ===== SQLite =====
    file_table_name: str = "FILES_METADATA"
    conversion_table_name: str = "CONVERSIONS_METADATA"
    conversion_relations_table_name: str = "CONVERSION_RELATIONS"

    # ===== Redis =====

    redis_url: str = "redis://redis:6379/0"

    # ===== Cleanup =====

    cleanup_ttl_hours: int = 72

    # ===== Server =====

    host: str = "YOUR_TRANSMUTE_HOST"
    port: int = 3313
    server_url: str | None = None

    def model_post_init(self, __context):
        """Compute derived paths after initialization."""

        self.db_path = self.data_dir / "db" / "app.db"
        self.upload_dir = self.data_dir / "uploads"
        self.output_dir = self.data_dir / "outputs"
        self.tmp_dir = self.data_dir / "tmp"

        self.server_url = f"http://{self.host}:{self.port}"

        # Ensure directories exist
        for path in [
            self.data_dir,
            self.db_path.parent,
            self.upload_dir,
            self.output_dir,
            self.tmp_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """
    Cached settings instance.

    Ensures we only construct settings once.
    """
    return Settings()