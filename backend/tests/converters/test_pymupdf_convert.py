from pathlib import Path

import fitz
from PIL import Image

from registry import registry


def test_png_to_pdf_uses_pymupdf_and_creates_pdf(tmp_path):
    source = tmp_path / 'sample.png'
    Image.new('RGBA', (24, 18), (255, 0, 0, 128)).save(source)

    converter_cls = registry.get_converter_for_conversion('png', 'pdf')
    assert converter_cls is not None
    assert converter_cls.__name__ == 'PyMuPDFConverter'

    output_dir = tmp_path / 'output'
    converter = converter_cls(
        input_file=str(source),
        output_dir=str(output_dir),
        input_type='png',
        output_type='pdf',
    )

    output_files = converter.convert()

    assert len(output_files) == 1
    output_path = Path(output_files[0])
    assert output_path.exists()
    assert output_path.suffix == '.pdf'

    with fitz.open(output_path) as document:
        assert document.page_count == 1
        assert document[0].rect.width > 0
        assert document[0].rect.height > 0


def test_pdfa_to_pdf_is_supported_and_creates_pdf(tmp_path):
    source = tmp_path / 'sample.pdf'
    with fitz.open() as document:
        document.new_page(width=72, height=72)
        document.save(source)

    output_dir = tmp_path / 'output'
    converter = registry.get_converter('PyMuPDFConverter')(
        input_file=str(source),
        output_dir=str(output_dir),
        input_type='pdf/a',
        output_type='pdf',
    )

    assert converter.can_convert()

    output_files = converter.convert()

    assert len(output_files) == 1
    output_path = Path(output_files[0])
    assert output_path.exists()
    assert output_path.suffix == '.pdf'

    with fitz.open(output_path) as document:
        assert document.page_count == 1


def test_registry_prefers_pymupdf_for_pdfa_to_pdf():
    converter_cls = registry.get_converter_for_conversion('pdf/a', 'pdf')
    assert converter_cls is not None
    assert converter_cls.__name__ == 'PyMuPDFConverter'