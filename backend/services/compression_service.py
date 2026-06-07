"""Service layer for executing compressions.

This module isolates the actual work of running a compressor and persisting
its result so the same code path can be invoked from:

- The synchronous ``POST /api/compressions`` route.
- The background queue worker that processes ``CompressionJobDB`` entries.

Compression is same-format only: the output keeps the source's media type and
extension. The service does not raise ``HTTPException``; callers translate
exceptions into the appropriate error response (HTTP for the route,
``mark_failed`` for the worker).
"""
from __future__ import annotations

import errno
from pathlib import Path
import shutil
import uuid

from compressors import CompressorInterface
from core import (
    compute_sha256_checksum,
    delete_file_and_metadata,
    get_settings,
    media_type_extensions,
    validate_safe_path,
)
from db import (
    CompressionDB,
    CompressionRelationsDB,
    DefaultCompressionLevelsDB,
    FileDB,
    SettingsDB,
)


class CompressionFailedError(RuntimeError):
    """Raised when the underlying compressor fails to produce output."""


def _move_output_file(source_path: Path, target_path: Path) -> Path:
    """Persist a compressor output even when temp/output dirs are separate mounts."""
    try:
        return source_path.rename(target_path)
    except OSError as exc:
        if exc.errno != errno.EXDEV:
            raise

    shutil.move(str(source_path), str(target_path))
    return target_path


def run_compression_job(
    *,
    source_metadata: dict,
    compression_level: str | None,
    compressor_type: type[CompressorInterface],
    user_id: str,
    file_db: FileDB,
    compression_db: CompressionDB,
    compression_relations_db: CompressionRelationsDB,
    settings_db: SettingsDB,
    default_compression_levels_db: DefaultCompressionLevelsDB | None = None,
) -> dict:
    """Execute a compression and persist the resulting metadata.

    Args:
        source_metadata: Result of ``FileDB.get_file_metadata`` for the
            source file. Must already be ownership-checked by the caller.
        compression_level: Optional level preset (e.g. ``"light"``,
            ``"balanced"``, ``"max"``). If ``None`` and
            ``default_compression_levels_db`` is provided, the user's default
            for the source media format (if any) is applied.
        compressor_type: A compressor class returned by
            ``compressor_registry.get_compressor_for_format``.
        user_id: UUID of the owning user (the compressed file is stored
            under this user).
        file_db, compression_db, compression_relations_db, settings_db:
            Shared DB handles supplied by the caller.
        default_compression_levels_db: Optional handle used to resolve a
            default level when ``compression_level`` is ``None``.

    Returns:
        The compressed file metadata dict (including ``id``,
        ``storage_path``, ``size_bytes``, ``sha256_checksum``, and
        ``compression_level`` if used).

    Raises:
        CompressionFailedError: The compressor raised an exception or
            produced no output.
    """
    settings = get_settings()
    temp_dir = settings.tmp_dir
    compressed_dir = settings.output_dir

    validate_safe_path(source_metadata["storage_path"], raise_exception=True)

    # Compression is same-format: output keeps the source media type.
    media_format = source_metadata["media_type"]
    output_extension = f".{media_type_extensions.get(media_format, media_format)}"
    compressed_id = str(uuid.uuid4())

    # Resolve default compression level lazily so the user's current setting wins.
    if compression_level is None and default_compression_levels_db is not None:
        default_level = default_compression_levels_db.get(user_id, media_format)
        if default_level:
            compression_level = default_level["compression_level"]

    compressor: CompressorInterface = compressor_type(
        source_metadata["storage_path"],
        f"{temp_dir}/",
        media_format,
    )

    try:
        output_files = compressor.compress(compression_level=compression_level)
    except Exception as exc:
        raise CompressionFailedError(str(exc)) from exc

    if not output_files:
        raise CompressionFailedError("Compressor produced no output files")

    moved_output_file = _move_output_file(
        Path(output_files[0]),
        Path(f"{compressed_dir}/{compressed_id}{output_extension}"),
    )

    compressed_metadata = dict(source_metadata)
    compressed_metadata["id"] = compressed_id
    compressed_metadata["media_type"] = media_format
    compressed_metadata["extension"] = output_extension
    compressed_metadata["storage_path"] = str(moved_output_file)
    compressed_metadata["size_bytes"] = moved_output_file.stat().st_size
    compressed_metadata["sha256_checksum"] = compute_sha256_checksum(moved_output_file)
    compressed_metadata["user_id"] = user_id
    compressed_metadata.pop("created_at", None)
    if compression_level:
        compressed_metadata["compression_level"] = compression_level

    compression_db.insert_file_metadata(compressed_metadata)
    if compression_level:
        # ``insert_file_metadata`` pops compression_level off; re-attach for the return value.
        compressed_metadata["compression_level"] = compression_level

    compression_relations_db.insert_compression_relation({
        "original_file_id": source_metadata["id"],
        "compressed_file_id": compressed_id,
        "original_filename": source_metadata["original_filename"],
        "original_media_type": source_metadata["media_type"],
        "original_extension": source_metadata["extension"],
        "original_size_bytes": source_metadata["size_bytes"],
        "user_id": user_id,
    })

    if settings_db.get_settings(user_id).get("keep_originals", True) is False:
        delete_file_and_metadata(file_id=source_metadata["id"], file_db=file_db)

    return compressed_metadata
