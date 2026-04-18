from pydantic import BaseModel, Field
from typing import Literal, Optional


class ConversionRequest(BaseModel):
    id: str = Field(..., example="123e4567-e89b-12d3-a456-426614174000", description="ID of file to convert")
    quality: Optional[str] = Field(None, example="medium", description="Optional quality setting for conversion (e.g. low, medium, high)")
    output_format: str = Field(..., example="png", description="Target format for conversion")


class FileMetadata(BaseModel):
    id: str = Field(..., example="123e4567-e89b-12d3-a456-426614174000")
    storage_path: str = Field(..., example="data/uploads/6e36aefe-b129-436e-999d-f5037075c017.png")
    original_filename: str = Field(..., example="example.jpg")
    media_type: str = Field(..., example="jpg")
    extension: str = Field(..., example=".jpg")
    size_bytes: int = Field(..., example=204800)
    sha256_checksum: str = Field(..., example="abc123def456...")
    user_id: str = Field(..., example="67118d71-a0c5-443c-80b5-e222bb63bfc2")
    compatible_formats: dict[str, list[str]] = Field(..., example={"png": [], "gif": [], "webp": ["low", "medium", "high"]}, description="Map of compatible output formats to their available quality options")


class FileMetadataWithFormats(FileMetadata):
    compatible_formats: dict[str, list[str]] = Field(..., example={"png": [], "gif": [], "webp": ["low", "medium", "high"]}, description="Map of compatible output formats to their available quality options")


class ConversionItem(BaseModel):
    id: str = Field(..., example="123e4567-e89b-12d3-a456-426614174000")
    original_filename: str = Field(..., example="example.jpg")
    media_type: str = Field(..., example="png")
    extension: str = Field(..., example=".png")
    size_bytes: int = Field(..., example=204800)
    sha256_checksum: str = Field(..., example="abc123def456...")
    quality: Optional[str] = Field(None, example="medium", description="Quality setting used for this conversion")
    original_file: Optional[FileMetadata] = Field(None, description="Original file metadata")


class ConversionListResponse(BaseModel):
    conversions: list[ConversionItem] = Field(..., description="List of completed conversions")

class ConverterMetadata(BaseModel):
    name: str = Field(..., example="drawio_convert")
    supported_input_formats: list[str] = Field(..., example=["drawio"])
    supported_output_formats: list[str] = Field(..., example=["png", "pdf", "jpg"])
    formats_with_qualities: list[str] = Field(..., example=["jpeg"], description="Output formats that support quality options")
    qualities: list[str] = Field(..., example=["low", "medium", "high"], description="Available quality levels")

class ConverterMetadataListResponse(BaseModel):
    converters: list[ConverterMetadata] = Field(..., description="List of the available converters")

class ErrorResponse(BaseModel):
    detail: str = Field(..., example="No converter found for jpg to png", description="Error message")


class AppInfo(BaseModel):
    name: str = Field(..., example="Transmute", description="Application name")
    version: str = Field(..., example="v1.0.0", description="Application version")


class HealthStatus(BaseModel):
    status: str = Field(..., example="alive", description="Health status")


class ReadinessChecks(BaseModel):
    database: str = Field(..., example="ok", description="Database check status")
    storage: str = Field(..., example="ok", description="Storage check status")


class ReadinessResponse(BaseModel):
    status: str = Field(..., example="ready", description="Overall readiness status")
    checks: ReadinessChecks = Field(..., description="Individual component checks")


class FileListResponse(BaseModel):
    files: list[FileMetadata] = Field(..., description="List of uploaded files")


class UrlUploadRequest(BaseModel):
    url: str = Field(..., example="https://example.com/file.pdf", description="Direct URL to a file for Transmute to download")


class FileUploadResponse(BaseModel):
    message: str = Field(..., example="File uploaded successfully", description="Upload status message")
    metadata: FileMetadataWithFormats = Field(..., description="Uploaded file metadata with compatible formats")


class FileDeleteResponse(BaseModel):
    message: str = Field(..., example="File deleted successfully", description="Deletion status message")


class BatchDownloadRequest(BaseModel):
    file_ids: list[str] = Field(..., example=["123e4567-e89b-12d3-a456-426614174000", "987fcdeb-51a2-43f1-b789-123456789abc"], description="List of converted file IDs to download")


ThemeValue = Literal["rubedo", "citrinitas", "viriditas", "nigredo", "albedo", "aurora", "caelum", "argentum"]
UserRoleValue = Literal["admin", "member", "guest"]


class AppSettingsResponse(BaseModel):
    theme: ThemeValue = Field(..., example="rubedo", description="Active UI theme")
    auto_download: bool = Field(..., example=False, description="Auto-download converted files on completion")
    keep_originals: bool = Field(..., example=True, description="Retain uploaded source files after conversion")
    cleanup_enabled: bool = Field(..., example=True, description="Enable automatic cleanup of old files")
    cleanup_ttl_minutes: int = Field(..., example=60, description="Time-to-live in minutes for cleanup")


class AppSettingsUpdate(BaseModel):
    theme: Optional[ThemeValue] = Field(None, example="rubedo", description="UI theme to apply")
    auto_download: Optional[bool] = Field(None, example=False, description="Auto-download on completion")
    keep_originals: Optional[bool] = Field(None, example=True, description="Keep original files after conversion")
    cleanup_enabled: Optional[bool] = Field(None, example=True, description="Enable automatic cleanup of old files")
    cleanup_ttl_minutes: Optional[int] = Field(None, example=60, description="Time-to-live in minutes for cleanup")


class DefaultFormatMapping(BaseModel):
    input_format: str = Field(..., example="png", description="Input file format")
    output_format: str = Field(..., example="jpeg", description="Default output format")


class DefaultFormatListResponse(BaseModel):
    defaults: list[DefaultFormatMapping] = Field(..., description="List of default format mappings")
    aliases: dict[str, str] = Field(..., description="Format alias map (e.g. jpg -> jpeg)")


class DefaultQualityMapping(BaseModel):
    output_format: str = Field(..., example="jpeg", description="Output file format")
    quality: str = Field(..., example="high", description="Default quality level")


class DefaultQualityListResponse(BaseModel):
    defaults: list[DefaultQualityMapping] = Field(..., description="List of default quality mappings")


class UserResponse(BaseModel):
    uuid: str = Field(..., example="123e4567-e89b-12d3-a456-426614174000", description="Stable user UUID")
    username: str = Field(..., example="alice", description="Unique account username")
    email: Optional[str] = Field(None, example="alice@example.com", description="Optional email address")
    full_name: Optional[str] = Field(None, example="Alice Example", description="Optional full name")
    role: UserRoleValue = Field(..., example="member", description="Assigned role")
    disabled: bool = Field(..., example=False, description="Whether the account is disabled")
    is_guest: bool = Field(False, example=False, description="Whether this is a guest account")
    has_usable_password: bool = Field(True, example=True, description="Whether the account has a local password (false for OIDC-only accounts)")


class UserListResponse(BaseModel):
    users: list[UserResponse] = Field(..., description="List of users")


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=1, example="alice", description="Unique account username")
    email: Optional[str] = Field(None, example="alice@example.com", description="Optional email address")
    full_name: Optional[str] = Field(None, example="Alice Example", description="Optional full name")
    password: str = Field(..., min_length=8, example="correct horse battery staple", description="Plain-text password (min 8 characters)")
    role: UserRoleValue = Field("member", example="member", description="Assigned role")
    disabled: bool = Field(False, example=False, description="Whether the account starts disabled")


class UserUpdateRequest(BaseModel):
    username: Optional[str] = Field(None, min_length=1, example="alice", description="Unique account username")
    email: Optional[str] = Field(None, example="alice@example.com", description="Optional email address")
    full_name: Optional[str] = Field(None, example="Alice Example", description="Optional full name")
    password: Optional[str] = Field(None, min_length=8, example="new secure password", description="New plain-text password (min 8 characters)")
    role: Optional[UserRoleValue] = Field(None, example="admin", description="Assigned role")
    disabled: Optional[bool] = Field(None, example=False, description="Whether the account is disabled")


class UserAuthRequest(BaseModel):
    username: str = Field(..., min_length=1, example="alice", description="Username to authenticate")
    password: str = Field(..., min_length=1, example="correct horse battery staple", description="Plain-text password to verify")


class UserAuthResponse(BaseModel):
    access_token: str = Field(..., example="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...", description="Signed JWT access token")
    token_type: str = Field(..., example="bearer", description="OAuth2 token type")
    expires_in: int = Field(..., example=3600, description="Token lifetime in seconds")
    user: UserResponse = Field(..., description="Authenticated user details")


class UserDeleteResponse(BaseModel):
    message: str = Field(..., example="User deleted successfully", description="Deletion status message")


class UserBootstrapStatusResponse(BaseModel):
    requires_setup: bool = Field(..., example=True, description="Whether the first admin account still needs to be created")
    user_count: int = Field(..., example=0, description="Current number of users")


class UserSelfUpdateRequest(BaseModel):
    username: Optional[str] = Field(None, min_length=1, example="alice", description="Unique account username")
    email: Optional[str] = Field(None, example="alice@example.com", description="Optional email address")
    full_name: Optional[str] = Field(None, example="Alice Example", description="Optional full name")
    password: Optional[str] = Field(None, min_length=8, example="new secure password", description="New plain-text password (min 8 characters)")


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, example="CI pipeline", description="Human-readable label for the key")


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
    user_uuid: str = Field(..., example="123e4567-e89b-12d3-a456-426614174000", description="User UUID")
    username: str = Field(..., example="alice", description="Username")
    files_uploaded: int = Field(..., example=12, description="Number of files uploaded")
    conversions: int = Field(..., example=8, description="Number of conversions performed")
    storage_bytes: int = Field(..., example=10485760, description="Total storage used in bytes (uploads + conversions)")


class StatsResponse(BaseModel):
    total_files_uploaded: int = Field(..., example=42, description="Total files uploaded across all users")
    total_conversions: int = Field(..., example=30, description="Total conversions across all users")
    total_storage_bytes: int = Field(..., example=104857600, description="Total storage used in bytes across all users")
    users: list[UserStatsItem] = Field(..., description="Per-user breakdown of stats")