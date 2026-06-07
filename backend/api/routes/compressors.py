from fastapi import APIRouter, Depends

from api.deps import get_current_active_user
from api.schemas import CompressorMetadataListResponse
from registry import compressor_registry

router = APIRouter(prefix="/compressors", tags=["compressors"], dependencies=[Depends(get_current_active_user)])


@router.get(
    "",
    summary="List all available compressors",
    responses={
        200: {
            "model": CompressorMetadataListResponse,
            "description": "List of compressors with the formats and compression levels they support",
        }
    }
)
def list_compressors():
    compressors = []

    for name, compressor_class in compressor_registry.compressors.items():
        compressors.append({
            "name": name,
            "supported_formats": sorted(getattr(compressor_class, 'supported_formats', set())),
            "formats_with_compression_levels": sorted(compressor_class.get_formats_with_compression_levels()),
            "compression_levels": sorted(compressor_class.get_compression_levels()),
        })
    return {"compressors": compressors}
