import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse
from pydantic import Field, field_validator
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
    domain_auth_config_path: Path = Field(default=Path("domain_auth/config.json"))
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
    conversion_jobs_table_name: str = "CONVERSION_JOBS"
    compression_table_name: str = "COMPRESSIONS_METADATA"
    compression_relations_table_name: str = "COMPRESSION_RELATIONS"
    compression_jobs_table_name: str = "COMPRESSION_JOBS"
    app_settings_table_name: str = "APP_SETTINGS"
    custom_themes_table_name: str = "CUSTOM_THEMES"
    user_table_name: str = "USERS"

    # ===== Conversion queue =====
    # Number of background worker threads.
    conversion_worker_concurrency: int = 5
    # If a `running` job exists at startup, it's stale (process restarted mid-job).
    # Such jobs are marked failed during recovery on app boot.
    conversion_job_stale_after_minutes: int = 60

    # ===== Compression queue =====
    # Number of background worker threads for the compression queue.
    compression_worker_concurrency: int = 5

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
    oidc_username_claim: str = "preferred_username"
    oidc_auto_create_users: bool = True
    oidc_auto_launch: bool = False  # If True, automatically redirect to OIDC login when accessing /auth

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
    hosts: list[str] | None = None
    port: int = 3313
    api_server_url: str | None = None

    # Reverse-proxy sub-path, derived from app_url's path (see model_post_init).
    root_path: str = ""

    @field_validator("oidc_issuer_url", "oidc_internal_url", "app_url", "oidc_username_claim", mode="before")
    @classmethod
    def _normalize_url_env(cls, value: str) -> str:
        """Strip whitespace and accidental surrounding quotes from string settings."""
        if not isinstance(value, str):
            return value

        normalized = value.strip()
        if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {'"', "'"}:
            normalized = normalized[1:-1].strip()
        return normalized

    @field_validator("hosts", mode="before")
    @classmethod
    def _normalize_hosts_env(cls, value):
        """Normalize host list from CSV or JSON array env forms."""
        if value is None:
            return None

        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                return None

            if normalized.startswith("["):
                try:
                    value = json.loads(normalized)
                except json.JSONDecodeError as exc:
                    raise ValueError("hosts must be a CSV string or JSON array of strings") from exc
            else:
                value = normalized.split(",")

        if isinstance(value, tuple):
            value = list(value)

        if not isinstance(value, list):
            raise ValueError("hosts must be a CSV string or JSON array of strings")

        parsed_hosts: list[str] = []
        for entry in value:
            if not isinstance(entry, str):
                raise ValueError("hosts entries must be strings")

            host = entry.strip()
            if len(host) >= 2 and host[0] == host[-1] and host[0] in {'"', "'"}:
                host = host[1:-1].strip()

            if host:
                parsed_hosts.append(host)

        return parsed_hosts or None

    def resolved_bind_host(self) -> str | list[str]:
        """Return the uvicorn host argument preserving legacy behavior by default."""
        return self.hosts if self.hosts else self.host

    def has_host_override_conflict(self) -> bool:
        """True when host was explicitly set but hosts will take precedence."""
        return bool(self.hosts) and "host" in self.model_fields_set

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

        # app_url=https://host/transmute -> "/transmute"; bare host -> "".
        self.root_path = urlparse(self.app_url).path.rstrip("/") if self.app_url else ""

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
