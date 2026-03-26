"""
Dynamic test suite that exercises every supported conversion path
using real sample files from assets/samples/.

For each sample file whose extension is recognized by the registry,
this module parametrizes a test case for every compatible output format.
The test copies the sample into a temporary directory, instantiates
the appropriate converter, runs the conversion, and asserts that at
least one non-empty output file is produced.
"""

import shutil
import uuid
from pathlib import Path

import pytest

from core import get_file_extension
from registry import registry

SAMPLES_DIR = Path(__file__).resolve().parents[3] / "assets" / "samples"


def _collect_conversion_cases() -> list[tuple[str, str, str]]:
    """
    Walk assets/samples/ and yield (sample_filename, input_format, output_format)
    tuples for every conversion the registry supports.
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

        input_fmt = registry.get_normalized_format(ext)
        compatible = registry.get_compatible_formats(input_fmt)

        for output_fmt in sorted(compatible):
            cases.append((sample.name, input_fmt, output_fmt))

    return cases


CONVERSION_CASES = _collect_conversion_cases()


@pytest.mark.parametrize(
    "sample_name, input_fmt, output_fmt",
    CONVERSION_CASES,
    ids=[f"{name}:{ifmt}->{ofmt}" for name, ifmt, ofmt in CONVERSION_CASES],
)
def test_conversion(sample_name, input_fmt, output_fmt, safe_path_test_settings):
    """Convert a sample file to every compatible output format."""
    src = SAMPLES_DIR / sample_name

    # Place the file inside the uploads dir with a hex filename so that
    # validate_safe_path (called by some converters) is satisfied.
    ext = get_file_extension(sample_name)
    hex_name = uuid.uuid4().hex
    dest = safe_path_test_settings.upload_dir / (f"{hex_name}.{ext}" if ext else hex_name)
    shutil.copy2(src, dest)

    converter_cls = registry.get_converter_for_conversion(input_fmt, output_fmt)
    assert converter_cls is not None, (
        f"Registry returned no converter for {input_fmt} -> {output_fmt}"
    )

    output_dir = safe_path_test_settings.output_dir

    converter = converter_cls(
        input_file=str(dest),
        output_dir=str(output_dir),
        input_type=input_fmt,
        output_type=output_fmt,
    )

    assert converter.can_convert(), (
        f"{converter_cls.__name__} reports it cannot convert {input_fmt} -> {output_fmt}"
    )

    output_files = converter.convert()

    assert output_files, "convert() returned an empty list"
    for fpath in output_files:
        p = Path(fpath)
        assert p.exists(), f"Output file does not exist: {fpath}"
        assert p.stat().st_size > 0, f"Output file is empty: {fpath}"
