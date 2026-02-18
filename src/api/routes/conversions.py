import json
from pathlib import Path
import uuid
import hashlib
from fastapi import APIRouter, Request
from converters import ConverterInterface
from registry import ConverterRegistry
from core import get_settings
from db import ConversionDB, FileDB


router = APIRouter(prefix="/conversions", tags=["conversions"])
regisitry = ConverterRegistry()
settings = get_settings()
UPLOAD_DIR = settings.upload_dir
TEMP_DIR = settings.tmp_dir
CONVERTED_DIR = settings.output_dir

@router.get("/")
def list_conversions():
    return {"conversions": []}

@router.post("/")
async def create_conversion(request: Request):
    body = await request.json()
    file_db = FileDB()
    conversion_db = ConversionDB()

    og_id = body.get("id")
    input_format = body.get("input_format")
    output_format = body.get("output_format")
    og_metadata = file_db.get_file_metadata(og_id)
    print(og_metadata)
    converted_id = str(uuid.uuid4())
    converted_metadata = dict(og_metadata)

    # Ensure the original file was uploaded and exists in the database
    if og_metadata is None:
        return {"error": f"No file found with id {og_id}"}
    
    # Find the appropriate converter for this conversion
    converter_type = regisitry.get_converter_for_conversion(input_format, output_format)
    if converter_type is None:
        return {"error": f"No converter found for {input_format} to {output_format}"}

    converter: ConverterInterface = converter_type(f'{UPLOAD_DIR}/{og_id}.{input_format}', f'{TEMP_DIR}/', input_format, output_format)
    output_files = converter.convert()
    moved_output_file = Path(output_files[0]).rename(f'{CONVERTED_DIR}/{converted_id}.{output_format}')

    converted_metadata['id'] = converted_id
    converted_metadata['media_type'] = f"{output_format}"
    converted_metadata['extension'] = f".{output_format}"
    converted_metadata['storage_path'] = str(moved_output_file)
    converted_metadata['size_bytes'] = moved_output_file.stat().st_size
    converted_metadata['sha256_checksum'] = hashlib.sha256(moved_output_file.read_bytes()).hexdigest()
    converted_metadata.pop('created_at', None)  # Remove created_at from original metadata if it exists
    conversion_db.insert_file_metadata(converted_metadata)

    return {"message": "Conversion created"}