from typing import Type
from fastapi import APIRouter, Depends

from api.deps import get_current_active_user
from api.schemas import ConverterMetadataListResponse
from converters import ConverterInterface
from registry import registry

router = APIRouter(prefix="/converters", tags=["converters"], dependencies=[Depends(get_current_active_user)])

@router.get(
    "",
    summary="List all available converters",
    responses={
        200: {
            "model": ConverterMetadataListResponse,
            "description": "List of converters with supported input and output formats",
        }
    }
)
def list_converters():
    converters = []
    
    for name, converter_class in registry.converters.items():
        supported_input_formats = []
        supported_output_formats = []

        if hasattr(converter_class, 'supported_input_formats'):
            supported_input_formats = list(converter_class.supported_input_formats)
        else:
            supported_input_formats = []

        if hasattr(converter_class, 'supported_output_formats'):
            supported_output_formats = list(converter_class.supported_output_formats)
        else:
            supported_output_formats = []

        converter_item = {
            "name": name,
            "supported_input_formats": supported_input_formats,
            "supported_output_formats": supported_output_formats,
        }
        converters.append(converter_item)
    return {"converters": converters}