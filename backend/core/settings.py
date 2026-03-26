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
    app_version: str = Field(default="dev")

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
    app_settings_table_name: str = "APP_SETTINGS"
    user_table_name: str = "USERS"

    # ===== Authentication =====
    auth_secret_key: str = ""
    auth_algorithm: str = "HS256"
    auth_access_token_expire_minutes: int = 60

    # ===== OIDC (optional) =====
    oidc_issuer_url: str = ""
    oidc_internal_url: str = ""  # Backend-to-provider URL (for Docker); falls back to oidc_issuer_url
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_display_name: str = "SSO"
    oidc_auto_create_users: bool = True

    # ===== Guest Access =====
    allow_unauthenticated: bool = False

    # ===== Server =====

    # http://192.168.1.1:3313
    # https://transmute.yourdomain.com
    # etc. Used for constructing URLs in OIDC API response etc.

    # Not strictly required, but recommended to set if running behind a reverse
    # proxy or if the app should be reachable at a different URL than http://{host}:{port}
    app_url: str = ""

    # Binding to all interfaces is required as this app should be reachable from
    # other machines besides just localhost
    host: str = "0.0.0.0"  # nosec B104
    port: int = 3313
    api_server_url: str | None = None

    def model_post_init(self, __context):
        """Compute derived paths after initialization."""

        if not self.auth_secret_key:
            import secrets
            object.__setattr__(self, 'auth_secret_key', secrets.token_urlsafe(64))

        self.db_path = self.data_dir / "db" / "app.db"
        self.upload_dir = self.data_dir / "uploads"
        self.output_dir = self.data_dir / "outputs"
        self.tmp_dir = self.data_dir / "tmp"

        self.api_server_url = self.app_url if self.app_url else f"http://{self.host}:{self.port}"

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