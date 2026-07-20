from typing import Literal, Optional

from pydantic import BaseModel, Field


class ConversionRequest(BaseModel):
    id: str = Field(..., description="ID of file to convert", json_schema_extra={"example": "123e4567-e89b-12d3-a456-426614174000"})
    quality: Optional[str] = Field(None, description="Optional quality setting for conversion (e.g. low, medium, high)", json_schema_extra={"example": "medium"})
    output_format: str = Field(..., description="Target format for conversion", json_schema_extra={"example": "png"})


ConversionJobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]


class ConversionJobCreateRequest(BaseModel):
    id: str = Field(..., description="ID of the source file to convert", json_schema_extra={"example": "123e4567-e89b-12d3-a456-426614174000"})
    output_format: str = Field(..., description="Target format for conversion", json_schema_extra={"example": "png"})
    quality: Optional[str] = Field(None, description="Optional quality setting (e.g. low, medium, high)", json_schema_extra={"example": "medium"})


class ConversionJobResponse(BaseModel):
    id: str = Field(..., description="Job UUID")
    user_id: str = Field(..., description="Owning user UUID")
    source_file_id: str = Field(..., description="Source file ID being converted")
    output_format: str = Field(..., description="Target output format")
    quality: Optional[str] = Field(None, description="Quality option used, if any")
    status: ConversionJobStatus = Field(..., description="Current job status")
    progress: Optional[int] = Field(None, description="0-100 progress hint when available")
    error_message: Optional[str] = Field(None, description="Error message when status is failed")
    output_file_id: Optional[str] = Field(None, description="ID of the resulting converted file when completed")
    converter_name: Optional[str] = Field(None, description="Converter implementation that handled (or will handle) the job")
    source_filename: Optional[str] = Field(None, description="Denormalized source filename at submit time")
    source_media_type: Optional[str] = Field(None, description="Denormalized source media type at submit time")
    source_extension: Optional[str] = Field(None, description="Denormalized source extension at submit time")
    source_size_bytes: Optional[int] = Field(None, description="Denormalized source size at submit time")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    started_at: Optional[str] = Field(None, description="Time the worker began processing")
    completed_at: Optional[str] = Field(None, description="Time the job reached a terminal status")
    updated_at: Optional[str] = Field(None, description="Last update timestamp")


class ConversionJobListResponse(BaseModel):
    jobs: list[ConversionJobResponse] = Field(..., description="List of conversion jobs for the current user")


class FileMetadata(BaseModel):
    id: str = Field(..., json_schema_extra={"example": "123e4567-e89b-12d3-a456-426614174000"})
    storage_path: str = Field(..., json_schema_extra={"example": "data/uploads/6e36aefe-b129-436e-999d-f5037075c017.png"})
    original_filename: str = Field(..., json_schema_extra={"example": "example.jpg"})
    media_type: str = Field(..., json_schema_extra={"example": "jpg"})
    extension: str = Field(..., json_schema_extra={"example": ".jpg"})
    size_bytes: int = Field(..., json_schema_extra={"example": 204800})
    sha256_checksum: str = Field(..., json_schema_extra={"example": "abc123def456..."})
    user_id: str = Field(..., json_schema_extra={"example": "67118d71-a0c5-443c-80b5-e222bb63bfc2"})
    compatible_formats: dict[str, list[str]] = Field(..., description="Map of compatible output formats to their available quality options", json_schema_extra={"example": {"png": [], "gif": [], "webp": ["low", "medium", "high"]}})


class FileMetadataWithFormats(FileMetadata):
    compatible_formats: dict[str, list[str]] = Field(..., description="Map of compatible output formats to their available quality options", json_schema_extra={"example": {"png": [], "gif": [], "webp": ["low", "medium", "high"]}})


class ConversionItem(BaseModel):
    id: str = Field(..., json_schema_extra={"example": "123e4567-e89b-12d3-a456-426614174000"})
    original_filename: str = Field(..., json_schema_extra={"example": "example.jpg"})
    media_type: str = Field(..., json_schema_extra={"example": "png"})
    extension: str = Field(..., json_schema_extra={"example": ".png"})
    size_bytes: int = Field(..., json_schema_extra={"example": 204800})
    sha256_checksum: str = Field(..., json_schema_extra={"example": "abc123def456..."})
    quality: Optional[str] = Field(None, description="Quality setting used for this conversion", json_schema_extra={"example": "medium"})
    original_file: Optional[FileMetadata] = Field(None, description="Original file metadata")


class ConversionListResponse(BaseModel):
    conversions: list[ConversionItem] = Field(..., description="List of completed conversions")

class ConverterMetadata(BaseModel):
    name: str = Field(..., json_schema_extra={"example": "drawio_convert"})
    supported_input_formats: list[str] = Field(..., json_schema_extra={"example": ["drawio"]})
    supported_output_formats: list[str] = Field(..., json_schema_extra={"example": ["png", "pdf", "jpg"]})
    formats_with_qualities: list[str] = Field(..., description="Output formats that support quality options", json_schema_extra={"example": ["jpeg"]})
    qualities: list[str] = Field(..., description="Available quality levels", json_schema_extra={"example": ["low", "medium", "high"]})

class ConverterMetadataListResponse(BaseModel):
    converters: list[ConverterMetadata] = Field(..., description="List of the available converters")

class CompressorMetadata(BaseModel):
    name: str = Field(..., json_schema_extra={"example": "image_compress"})
    supported_formats: list[str] = Field(..., description="Media formats this compressor can compress (input == output)", json_schema_extra={"example": ["jpeg", "png"]})
    formats_with_compression_levels: list[str] = Field(..., description="Subset of supported formats that honor a compression-level preset", json_schema_extra={"example": ["jpeg"]})
    compression_levels: list[str] = Field(..., description="Available compression-level presets", json_schema_extra={"example": ["light", "balanced", "max"]})

class CompressorMetadataListResponse(BaseModel):
    compressors: list[CompressorMetadata] = Field(..., description="List of the available compressors")

class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Error message", json_schema_extra={"example": "No converter found for jpg to png"})


class AppInfo(BaseModel):
    name: str = Field(..., description="Application name", json_schema_extra={"example": "Transmute"})
    version: str = Field(..., description="Application version", json_schema_extra={"example": "v1.0.0"})


class HealthStatus(BaseModel):
    status: str = Field(..., description="Health status", json_schema_extra={"example": "alive"})


class ReadinessChecks(BaseModel):
    database: str = Field(..., description="Database check status", json_schema_extra={"example": "ok"})
    storage: str = Field(..., description="Storage check status", json_schema_extra={"example": "ok"})


class ReadinessResponse(BaseModel):
    status: str = Field(..., description="Overall readiness status", json_schema_extra={"example": "ready"})
    checks: ReadinessChecks = Field(..., description="Individual component checks")


class FileListResponse(BaseModel):
    files: list[FileMetadata] = Field(..., description="List of uploaded files")


class UrlUploadRequest(BaseModel):
    url: str = Field(..., description="Direct URL to a file for Transmute to download", json_schema_extra={"example": "https://example.com/file.pdf"})


class FileUploadResponse(BaseModel):
    message: str = Field(..., description="Upload status message", json_schema_extra={"example": "File uploaded successfully"})
    metadata: FileMetadataWithFormats = Field(..., description="Uploaded file metadata with compatible formats")


class FileUrlUploadResponse(BaseModel):
    message: str = Field(..., description="Upload status message", json_schema_extra={"example": "File uploaded successfully"})
    files: list[FileMetadataWithFormats] = Field(..., description="Metadata for every file retrieved from the URL. A single URL may resolve to multiple files (e.g. a playlist).")


class FileDeleteResponse(BaseModel):
    message: str = Field(..., description="Deletion status message", json_schema_extra={"example": "File deleted successfully"})


class BatchDownloadRequest(BaseModel):
    file_ids: list[str] = Field(..., description="List of converted file IDs to download", json_schema_extra={"example": ["123e4567-e89b-12d3-a456-426614174000", "987fcdeb-51a2-43f1-b789-123456789abc"]})


ThemeValue = Literal["rubedo", "citrinitas", "viriditas", "nigredo", "albedo", "aurora", "caelum", "argentum"]
ThemeModeValue = Literal["manual", "system"]
UserRoleValue = Literal["admin", "member", "guest"]


class AppSettingsResponse(BaseModel):
    theme: str = Field(..., description="Active UI theme key (built-in or custom)", json_schema_extra={"example": "rubedo"})
    theme_mode: ThemeModeValue = Field(..., description="Whether to use one theme or follow the system appearance", json_schema_extra={"example": "manual"})
    light_theme: str = Field(..., description="Theme key used for the system light appearance", json_schema_extra={"example": "albedo"})
    dark_theme: str = Field(..., description="Theme key used for the system dark appearance", json_schema_extra={"example": "rubedo"})
    auto_download: bool = Field(..., description="Auto-download converted files on completion", json_schema_extra={"example": False})
    keep_originals: bool = Field(..., description="Retain uploaded source files after conversion", json_schema_extra={"example": True})
    cleanup_enabled: bool = Field(..., description="Enable automatic cleanup of old files", json_schema_extra={"example": True})
    cleanup_ttl_minutes: int = Field(..., description="Time-to-live in minutes for cleanup", json_schema_extra={"example": 60})
    datetime_display_format: str = Field(..., description="Datetime display format pattern or 'locale'", json_schema_extra={"example": "DD/MM/YYYY - HH:mm:ss"})


class AppSettingsUpdate(BaseModel):
    theme: Optional[str] = Field(None, description="Theme key to apply (built-in or custom)", json_schema_extra={"example": "rubedo"})
    theme_mode: Optional[ThemeModeValue] = Field(None, description="Whether to use one theme or follow the system appearance", json_schema_extra={"example": "system"})
    light_theme: Optional[str] = Field(None, description="Theme key used for the system light appearance", json_schema_extra={"example": "albedo"})
    dark_theme: Optional[str] = Field(None, description="Theme key used for the system dark appearance", json_schema_extra={"example": "rubedo"})
    auto_download: Optional[bool] = Field(None, description="Auto-download on completion", json_schema_extra={"example": False})
    keep_originals: Optional[bool] = Field(None, description="Keep original files after conversion", json_schema_extra={"example": True})
    cleanup_enabled: Optional[bool] = Field(None, description="Enable automatic cleanup of old files", json_schema_extra={"example": True})
    cleanup_ttl_minutes: Optional[int] = Field(None, description="Time-to-live in minutes for cleanup", json_schema_extra={"example": 60})
    datetime_display_format: Optional[str] = Field(None, description="Datetime display format pattern or 'locale'", json_schema_extra={"example": "DD/MM/YYYY - HH:mm:ss"})


# Hex color regex: #rgb or #rrggbb
_HEX_COLOR_PATTERN = r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$"


class CustomThemeColors(BaseModel):
    primary:       str = Field(..., pattern=_HEX_COLOR_PATTERN, description="Primary brand color", json_schema_extra={"example": "#ef4444"})
    primary_light: str = Field(..., pattern=_HEX_COLOR_PATTERN, description="Lighter primary variant", json_schema_extra={"example": "#f87171"})
    primary_dark:  str = Field(..., pattern=_HEX_COLOR_PATTERN, description="Darker primary variant", json_schema_extra={"example": "#b91c1c"})
    accent:        str = Field(..., pattern=_HEX_COLOR_PATTERN, description="Accent color", json_schema_extra={"example": "#f59e0b"})
    success:       str = Field(..., pattern=_HEX_COLOR_PATTERN, description="Success color", json_schema_extra={"example": "#22c55e"})
    success_light: str = Field(..., pattern=_HEX_COLOR_PATTERN, description="Lighter success variant", json_schema_extra={"example": "#4ade80"})
    success_dark:  str = Field(..., pattern=_HEX_COLOR_PATTERN, description="Darker success variant", json_schema_extra={"example": "#15803d"})
    surface_dark:  str = Field(..., pattern=_HEX_COLOR_PATTERN, description="Dark surface background", json_schema_extra={"example": "#0f172a"})
    surface_light: str = Field(..., pattern=_HEX_COLOR_PATTERN, description="Light surface background", json_schema_extra={"example": "#1e293b"})
    text:          str = Field(..., pattern=_HEX_COLOR_PATTERN, description="Primary text color", json_schema_extra={"example": "#f8fafc"})
    text_muted:    str = Field(..., pattern=_HEX_COLOR_PATTERN, description="Muted text color", json_schema_extra={"example": "#cbd5e1"})


class CustomThemeResponse(BaseModel):
    key:        str = Field(..., description="Stable URL-safe identifier", json_schema_extra={"example": "my-theme"})
    name:       str = Field(..., description="Human-readable display name", json_schema_extra={"example": "My Theme"})
    colors:     CustomThemeColors = Field(..., description="Color token values (hex)")
    created_by: Optional[str] = Field(None, description="UUID of the user that created the theme")
    created_at: Optional[str] = Field(None, description="ISO-8601 creation timestamp")
    updated_at: Optional[str] = Field(None, description="ISO-8601 last-update timestamp")


class CustomThemeListResponse(BaseModel):
    themes:   list[CustomThemeResponse] = Field(..., description="All custom themes registered in the database")
    builtins: list[str] = Field(..., description="Built-in theme keys defined by the application")


class CustomThemeCreateRequest(BaseModel):
    name:   str = Field(..., min_length=1, max_length=64, description="Display name", json_schema_extra={"example": "My Theme"})
    colors: CustomThemeColors = Field(..., description="Color token payload (every token is required)")


class CustomThemeUpdateRequest(BaseModel):
    name:   Optional[str] = Field(None, min_length=1, max_length=64, description="New display name", json_schema_extra={"example": "My Theme"})
    colors: Optional[CustomThemeColors] = Field(None, description="Replacement color token payload")


class DefaultFormatMapping(BaseModel):
    input_format: str = Field(..., description="Input file format", json_schema_extra={"example": "png"})
    output_format: str = Field(..., description="Default output format", json_schema_extra={"example": "jpeg"})


class DefaultFormatListResponse(BaseModel):
    defaults: list[DefaultFormatMapping] = Field(..., description="List of default format mappings")
    aliases: dict[str, str] = Field(..., description="Format alias map (e.g. jpg -> jpeg)")


class DefaultQualityMapping(BaseModel):
    output_format: str = Field(..., description="Output file format", json_schema_extra={"example": "jpeg"})
    quality: str = Field(..., description="Default quality level", json_schema_extra={"example": "high"})


class DefaultQualityListResponse(BaseModel):
    defaults: list[DefaultQualityMapping] = Field(..., description="List of default quality mappings")


class CompressionRequest(BaseModel):
    id: str = Field(..., description="ID of file to compress", json_schema_extra={"example": "123e4567-e89b-12d3-a456-426614174000"})
    compression_level: Optional[str] = Field(None, description="Optional compression-level preset (e.g. light, balanced, max)", json_schema_extra={"example": "balanced"})


CompressionJobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]


class CompressionJobCreateRequest(BaseModel):
    id: str = Field(..., description="ID of the source file to compress", json_schema_extra={"example": "123e4567-e89b-12d3-a456-426614174000"})
    compression_level: Optional[str] = Field(None, description="Optional compression-level preset (e.g. light, balanced, max)", json_schema_extra={"example": "balanced"})


class CompressionJobResponse(BaseModel):
    id: str = Field(..., description="Job UUID")
    user_id: str = Field(..., description="Owning user UUID")
    source_file_id: str = Field(..., description="Source file ID being compressed")
    compression_level: Optional[str] = Field(None, description="Compression-level preset used, if any")
    status: CompressionJobStatus = Field(..., description="Current job status")
    progress: Optional[int] = Field(None, description="0-100 progress hint when available")
    error_message: Optional[str] = Field(None, description="Error message when status is failed")
    output_file_id: Optional[str] = Field(None, description="ID of the resulting compressed file when completed")
    compressor_name: Optional[str] = Field(None, description="Compressor implementation that handled (or will handle) the job")
    source_filename: Optional[str] = Field(None, description="Denormalized source filename at submit time")
    source_media_type: Optional[str] = Field(None, description="Denormalized source media type at submit time")
    source_extension: Optional[str] = Field(None, description="Denormalized source extension at submit time")
    source_size_bytes: Optional[int] = Field(None, description="Denormalized source size at submit time")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    started_at: Optional[str] = Field(None, description="Time the worker began processing")
    completed_at: Optional[str] = Field(None, description="Time the job reached a terminal status")
    updated_at: Optional[str] = Field(None, description="Last update timestamp")


class CompressionJobListResponse(BaseModel):
    jobs: list[CompressionJobResponse] = Field(..., description="List of compression jobs for the current user")


class CompressionItem(BaseModel):
    id: str = Field(..., json_schema_extra={"example": "123e4567-e89b-12d3-a456-426614174000"})
    original_filename: str = Field(..., json_schema_extra={"example": "example.jpg"})
    media_type: str = Field(..., json_schema_extra={"example": "jpg"})
    extension: str = Field(..., json_schema_extra={"example": ".jpg"})
    size_bytes: int = Field(..., json_schema_extra={"example": 102400})
    sha256_checksum: str = Field(..., json_schema_extra={"example": "abc123def456..."})
    compression_level: Optional[str] = Field(None, description="Compression-level preset used for this compression", json_schema_extra={"example": "balanced"})
    original_file: Optional[FileMetadata] = Field(None, description="Original file metadata")


class CompressionListResponse(BaseModel):
    compressions: list[CompressionItem] = Field(..., description="List of completed compressions")


class DefaultCompressionLevelMapping(BaseModel):
    media_format: str = Field(..., description="Media file format", json_schema_extra={"example": "jpeg"})
    compression_level: str = Field(..., description="Default compression-level preset", json_schema_extra={"example": "max"})


class DefaultCompressionLevelListResponse(BaseModel):
    defaults: list[DefaultCompressionLevelMapping] = Field(..., description="List of default compression-level mappings")



class UserResponse(BaseModel):
    uuid: str = Field(..., description="Stable user UUID", json_schema_extra={"example": "123e4567-e89b-12d3-a456-426614174000"})
    username: str = Field(..., description="Unique account username", json_schema_extra={"example": "alice"})
    email: Optional[str] = Field(None, description="Optional email address", json_schema_extra={"example": "alice@example.com"})
    full_name: Optional[str] = Field(None, description="Optional full name", json_schema_extra={"example": "Alice Example"})
    role: UserRoleValue = Field(..., description="Assigned role", json_schema_extra={"example": "member"})
    disabled: bool = Field(..., description="Whether the account is disabled", json_schema_extra={"example": False})
    is_guest: bool = Field(False, description="Whether this is a guest account", json_schema_extra={"example": False})
    has_usable_password: bool = Field(True, description="Whether the account has a local password (false for OIDC-only accounts)", json_schema_extra={"example": True})


class UserListResponse(BaseModel):
    users: list[UserResponse] = Field(..., description="List of users")


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=1, description="Unique account username", json_schema_extra={"example": "alice"})
    email: Optional[str] = Field(None, description="Optional email address", json_schema_extra={"example": "alice@example.com"})
    full_name: Optional[str] = Field(None, description="Optional full name", json_schema_extra={"example": "Alice Example"})
    password: str = Field(..., min_length=8, description="Plain-text password (min 8 characters)", json_schema_extra={"example": "correct horse battery staple"})
    role: UserRoleValue = Field("member", description="Assigned role", json_schema_extra={"example": "member"})
    disabled: bool = Field(False, description="Whether the account starts disabled", json_schema_extra={"example": False})


class UserUpdateRequest(BaseModel):
    username: Optional[str] = Field(None, min_length=1, description="Unique account username", json_schema_extra={"example": "alice"})
    email: Optional[str] = Field(None, description="Optional email address", json_schema_extra={"example": "alice@example.com"})
    full_name: Optional[str] = Field(None, description="Optional full name", json_schema_extra={"example": "Alice Example"})
    password: Optional[str] = Field(None, min_length=8, description="New plain-text password (min 8 characters)", json_schema_extra={"example": "new secure password"})
    role: Optional[UserRoleValue] = Field(None, description="Assigned role", json_schema_extra={"example": "admin"})
    disabled: Optional[bool] = Field(None, description="Whether the account is disabled", json_schema_extra={"example": False})


class UserAuthRequest(BaseModel):
    username: str = Field(..., min_length=1, description="Username to authenticate", json_schema_extra={"example": "alice"})
    password: str = Field(..., min_length=1, description="Plain-text password to verify", json_schema_extra={"example": "correct horse battery staple"})


class UserAuthResponse(BaseModel):
    access_token: str = Field(..., description="Signed JWT access token", json_schema_extra={"example": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."})
    token_type: str = Field(..., description="OAuth2 token type", json_schema_extra={"example": "bearer"})
    expires_in: int = Field(..., description="Token lifetime in seconds", json_schema_extra={"example": 3600})
    user: UserResponse = Field(..., description="Authenticated user details")


class UserDeleteResponse(BaseModel):
    message: str = Field(..., description="Deletion status message", json_schema_extra={"example": "User deleted successfully"})


class UserBootstrapStatusResponse(BaseModel):
    requires_setup: bool = Field(..., description="Whether the first admin account still needs to be created", json_schema_extra={"example": True})
    user_count: int = Field(..., description="Current number of users", json_schema_extra={"example": 0})


class UserSelfUpdateRequest(BaseModel):
    username: Optional[str] = Field(None, min_length=1, description="Unique account username", json_schema_extra={"example": "alice"})
    email: Optional[str] = Field(None, description="Optional email address", json_schema_extra={"example": "alice@example.com"})
    full_name: Optional[str] = Field(None, description="Optional full name", json_schema_extra={"example": "Alice Example"})
    password: Optional[str] = Field(None, min_length=8, description="New plain-text password (min 8 characters)", json_schema_extra={"example": "new secure password"})


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Human-readable label for the key", json_schema_extra={"example": "CI pipeline"})


class ApiKeyResponse(BaseModel):
    id: str = Field(..., description="Unique key identifier")
    user_uuid: str = Field(..., description="Owning user UUID")
    name: str = Field(..., description="Human-readable label")
    prefix: str = Field(..., description="First 8 characters of the key for identification")
    created_at: Optional[str] = Field(None, description="Creation timestamp")


class ApiKeyCreatedResponse(ApiKeyResponse):
    raw_key: str = Field(..., description="Full API key (shown only once)")


class ApiKeyListResponse(BaseModel):
    api_keys: list[ApiKeyResponse] = Field(..., description="List of API keys for the user")


class ApiKeyDeleteResponse(BaseModel):
    message: str = Field(..., description="Deletion status message")


class UserStatsItem(BaseModel):
    user_uuid: str = Field(..., description="User UUID", json_schema_extra={"example": "123e4567-e89b-12d3-a456-426614174000"})
    username: str = Field(..., description="Username", json_schema_extra={"example": "alice"})
    files_uploaded: int = Field(..., description="Number of files uploaded", json_schema_extra={"example": 12})
    output_files: int = Field(..., description="Number of output files produced (conversions + compressions)", json_schema_extra={"example": 8})
    storage_bytes: int = Field(..., description="Total storage used in bytes (uploads + conversions + compressions)", json_schema_extra={"example": 10485760})


class StatsResponse(BaseModel):
    total_files_uploaded: int = Field(..., description="Total files uploaded across all users", json_schema_extra={"example": 42})
    total_output_files: int = Field(..., description="Total output files produced across all users (conversions + compressions)", json_schema_extra={"example": 30})
    total_storage_bytes: int = Field(..., description="Total storage used in bytes across all users", json_schema_extra={"example": 104857600})
    users: list[UserStatsItem] = Field(..., description="Per-user breakdown of stats")
