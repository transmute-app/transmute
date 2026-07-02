"""Tests for custom CSS support in the pypandoc converter (Issue #212)."""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# WeasyPrint requires native libraries not available on all platforms.
# Mock it so the converters package can be imported without issues.
sys.modules.setdefault('weasyprint', MagicMock())

import pytest

from converters.pypandoc_convert import PyPandocConverter


class _FakeSettings:
    """Minimal settings stub for testing."""

    def __init__(self, pdf_custom_css_path: str = "", tmp_dir: Path | None = None):
        self.pdf_custom_css_path = pdf_custom_css_path
        self.tmp_dir = tmp_dir or Path(tempfile.mkdtemp())


def _make_converter(output_type: str = "pdf") -> PyPandocConverter:
    """Create a PyPandocConverter without requiring a real input file."""
    return PyPandocConverter(
        input_file="/tmp/fake-input.md",
        output_dir="/tmp",
        input_type="md",
        output_type=output_type,
    )


def test_pdf_css_defaults_to_builtin(tmp_path):
    """When no custom CSS path is set, the built-in default should be used."""
    converter = _make_converter()
    fake = _FakeSettings(pdf_custom_css_path="", tmp_dir=tmp_path / "tmp")
    with patch("converters.pypandoc_convert.get_settings", return_value=fake):
        css_path = converter._get_pdf_css_path()

    assert css_path is not None
    assert css_path.endswith("default-pdf.css")
    assert os.path.isfile(css_path)


def test_pdf_css_uses_custom_path(tmp_path):
    """When a valid custom CSS path is set, it should be used."""
    custom_css = tmp_path / "custom.css"
    custom_css.write_text("body { font-size: 10pt; }")

    converter = _make_converter()
    fake = _FakeSettings(pdf_custom_css_path=str(custom_css), tmp_dir=tmp_path / "tmp")
    with patch("converters.pypandoc_convert.get_settings", return_value=fake):
        css_path = converter._get_pdf_css_path()

    assert css_path is not None
    assert os.path.abspath(str(custom_css)) == css_path


def test_pdf_css_falls_back_when_custom_missing(tmp_path):
    """When the custom CSS path doesn't exist, fall back to the default."""
    converter = _make_converter()
    fake = _FakeSettings(
        pdf_custom_css_path=str(tmp_path / "nonexistent.css"),
        tmp_dir=tmp_path / "tmp",
    )
    with patch("converters.pypandoc_convert.get_settings", return_value=fake):
        css_path = converter._get_pdf_css_path()

    assert css_path is not None
    assert css_path.endswith("default-pdf.css")


def test_build_extra_args_includes_css_for_pdf(tmp_path):
    """The --css flag should be present in extra_args for PDF output."""
    converter = _make_converter(output_type="pdf")
    fake = _FakeSettings(pdf_custom_css_path="", tmp_dir=tmp_path / "tmp")

    # Create a minimal fake input file so resource-path resolution works
    fake_input = tmp_path / "input.md"
    fake_input.write_text("# Test")

    with patch("converters.pypandoc_convert.get_settings", return_value=fake):
        extra_args = converter._build_extra_args(str(fake_input))

    css_args = [a for a in extra_args if a.startswith("--css=")]
    assert len(css_args) == 1
    assert css_args[0].endswith("default-pdf.css") or "--css=" in css_args[0]


def test_build_extra_args_no_css_for_non_pdf(tmp_path):
    """The --css flag should NOT be present for non-PDF output (e.g. HTML)."""
    converter = _make_converter(output_type="html")
    fake = _FakeSettings(pdf_custom_css_path="", tmp_dir=tmp_path / "tmp")

    fake_input = tmp_path / "input.md"
    fake_input.write_text("# Test")

    with patch("converters.pypandoc_convert.get_settings", return_value=fake):
        extra_args = converter._build_extra_args(str(fake_input))

    css_args = [a for a in extra_args if a.startswith("--css=")]
    assert len(css_args) == 0