from pydantic import BaseModel, Field
from typing import Optional


class ConversionRequest(BaseModel):
    id: str = Field(..., example="123e4567-e89b-12d3-a456-426614174000", description="ID of file to convert")
    output_format: str = Field(..., example="png", description="Target format for conversion")


class FileMetadata(BaseModel):
    id: str = Field(..., example="123e4567-e89b-12d3-a456-426614174000")
    original_filename: str = Field(..., example="example.jpg")
    media_type: str = Field(..., example="jpg")
    extension: str = Field(..., example=".jpg")
    size_bytes: int = Field(..., example=204800)
    sha256_checksum: str = Field(..., example="abc123def456...")


class FileMetadataWithFormats(FileMetadata):
    compatible_formats: list[str] = Field(..., example=["png", "gif", "webp"], description="List of compatible output formats")


class ConversionItem(BaseModel):
    id: str = Field(..., example="123e4567-e89b-12d3-a456-426614174000")
    original_filename: str = Field(..., example="example.jpg")
    media_type: str = Field(..., example="jpg")
    extension: str = Field(..., example=".jpg")
    size_bytes: int = Field(..., example=204800)
    sha256_checksum: str = Field(..., example="abc123def456...")
    conversion: Optional[FileMetadata] = Field(None, description="Converted file metadata")


class ConversionListResponse(BaseModel):
    conversions: list[ConversionItem] = Field(..., description="List of completed conversions")


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


class FileUploadResponse(BaseModel):
    message: str = Field(..., example="File uploaded successfully", description="Upload status message")
    metadata: FileMetadataWithFormats = Field(..., description="Uploaded file metadata with compatible formats")


class FileDeleteResponse(BaseModel):
    message: str = Field(..., example="File deleted successfully", description="Deletion status message")
