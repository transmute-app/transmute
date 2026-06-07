"""
Dynamic test suite that exercises every supported compression path
using real sample files from assets/samples/.

For each sample file whose extension is recognized by the compressor
registry, this module parametrizes a test case for that format. The
test copies the sample into a temporary directory, instantiates the
appropriate compressor, runs the compression, and asserts that at
least one non-empty output file is produced.

This file is intentionally excluded from ``make test`` (see Makefile);
run it explicitly with::

    python3 -m pytest backend/tests/compressors/test_all_compressions.py
"""

import shutil
import uuid
from pathlib import Path

import pytest

from core import get_file_extension, detect_media_type
from registry import compressor_registry

SAMPLES_DIR = Path(__file__).resolve().parents[3] / "assets" / "samples"


def _collect_compression_cases() -> list[tuple[str, str, str]]:
    """
    Walk assets/samples/ and yield (sample_filename, media_format,
    compressor_name) tuples for every format the compressor registry supports.
    """
    cases: list[tuple[str, str, str]] = []
    if not SAMPLES_DIR.is_dir():
        return cases

    for sample in sorted(SAMPLES_DIR.iterdir()):
        if not sample.is_file():
            continue

        ext = get_file_extension(sample.name)
        if not ext:
            continue

        # Mirror the converter test: use detect_media_type for container
        # formats that need content inspection (e.g. p7m); otherwise use
        # the registry's extension-based normalization.
        if ext == 'p7m':
            media_fmt = detect_media_type(sample)
        else:
            media_fmt = compressor_registry.get_normalized_format(ext)

        compressor_cls = compressor_registry.get_compressor_for_format(media_fmt)
        if compressor_cls is None:
            continue

        cases.append((sample.name, media_fmt, compressor_cls.__name__))

    return cases


COMPRESSION_CASES = _collect_compression_cases()


@pytest.mark.parametrize(
    "sample_name, media_fmt, compressor_name",
    COMPRESSION_CASES,
    ids=[f"{cname}:{name}:{fmt}" for name, fmt, cname in COMPRESSION_CASES],
)
def test_compression(sample_name, media_fmt, compressor_name, safe_path_test_settings):
    """Compress a sample file using its registered compressor."""
    src = SAMPLES_DIR / sample_name

    # Place the file inside the uploads dir with a hex filename so that
    # validate_safe_path (called by some compressors) is satisfied.
    ext = get_file_extension(sample_name)
    hex_name = uuid.uuid4().hex
    dest = safe_path_test_settings.upload_dir / (f"{hex_name}.{ext}" if ext else hex_name)
    shutil.copy2(src, dest)

    compressor_cls = compressor_registry.get_compressor_for_format(media_fmt)
    assert compressor_cls is not None, (
        f"Registry returned no compressor for {media_fmt}"
    )

    output_dir = safe_path_test_settings.output_dir

    compressor = compressor_cls(
        input_file=str(dest),
        output_dir=str(output_dir),
        media_type=media_fmt,
    )

    assert compressor.can_compress(), (
        f"{compressor_cls.__name__} reports it cannot compress {media_fmt}"
    )

    # Run at the strongest preset to exercise the real compression path,
    # since we're just checking for non-empty output files.
    output_files = compressor.compress(compression_level="max")

    assert output_files, "compress() returned an empty list"
    for fpath in output_files:
        p = Path(fpath)
        assert p.exists(), f"Output file does not exist: {fpath}"
        assert p.stat().st_size > 0, f"Output file is empty: {fpath}"
