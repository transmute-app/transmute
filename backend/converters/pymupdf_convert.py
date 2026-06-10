import os
import shutil
import fitz  # PyMuPDF
import pymupdf4llm
import markdown
from io import BytesIO
from pathlib import Path
from typing import Optional

from PIL import Image
from pillow_heif import HeifImagePlugin
import pillow_avif  # noqa: F401 — registers AVIF plugin on import
import pillow_jxl   # noqa: F401 — registers JPEG XL plugin on import

from .converter_interface import ConverterInterface


# Raster image output formats supported via PyMuPDF page rendering + Pillow
# encoding. Multi-page PDFs produce one image per page; the service layer
# packages multi-file results into a single ZIP for download.
_RASTER_OUTPUT_FORMATS: set = {
    'png',
    'jpeg',
    'webp',
    'tiff',
    'bmp',
    'gif',
    'ppm',
    'pgm',
    'pbm',
    'tga',
    'jp2',
    'avif',
    'jxl',
    'ico',
    'dib',
    'pcx',
    'sgi',
    'pnm',
}

# Pillow save format names, when they differ from our format key.
_PILLOW_FORMAT_NAMES: dict = {
    'jpeg': 'JPEG',
    'jpg': 'JPEG',
    'png': 'PNG',
    'webp': 'WEBP',
    'tiff': 'TIFF',
    'bmp': 'BMP',
    'gif': 'GIF',
    'ppm': 'PPM',
    'pgm': 'PPM',
    'pbm': 'PPM',
    'pnm': 'PPM',
    'tga': 'TGA',
    'jp2': 'JPEG2000',
    'avif': 'AVIF',
    'jxl': 'JXL',
    'ico': 'ICO',
    'dib': 'DIB',
    'pcx': 'PCX',
    'sgi': 'SGI',
}

# Output formats that can encode quality settings.
_RASTER_QUALITY_FORMATS: set = {'jpeg', 'webp', 'avif', 'jxl', 'jp2'}

# Per-quality DPI used when rendering PDF pages to raster images.
_RASTER_QUALITY_DPI: dict = {
    'low': 100,
    'medium': 150,
    'high': 300,
}
_DEFAULT_RASTER_DPI = 150

_IMAGE_TO_PDF_INPUT_FORMATS: set = {
    'png',
    'jpeg',
    'webp',
    'tiff',
    'bmp',
    'gif',
    'ppm',
    'pgm',
    'pbm',
    'tga',
    'jp2',
    'avif',
    'jxl',
    'ico',
    'dib',
    'pcx',
    'sgi',
    'pnm',
    'heif',
    'heic',
}


class PyMuPDFConverter(ConverterInterface):
    """
    Converter for extracting content from PDF files using PyMuPDF.
    Supports converting PDFs to text, markdown, HTML, and raster images
    (one image per page).
    """

    supported_input_formats: set = {
        'pdf',
        'pdf/a',
        'pdf/x',
        'pdf/e',
        'pdf/ua',
        'pdf/vt',
    } | _IMAGE_TO_PDF_INPUT_FORMATS
    supported_output_formats: set = {
        'txt',
        'md',
        'html',
        'pdf',
    } | _RASTER_OUTPUT_FORMATS
    # Quality controls render DPI for raster outputs and encoder quality for
    # lossy formats, so every raster output advertises a quality option.
    formats_with_qualities = set(_RASTER_OUTPUT_FORMATS)

    def __init__(self, input_file: str, output_dir: str, input_type: str, output_type: str):
        """
        Initialize PyMuPDF converter.

        Args:
            input_file: Path to the input PDF file
            output_dir: Directory where the converted file will be saved
            input_type: Input file format (must be 'pdf')
            output_type: Output file format (e.g., 'txt', 'md', 'html')
        """
        super().__init__(input_file, output_dir, input_type, output_type)

    def can_convert(self) -> bool:
        """
        Check if the input file can be converted to the output format.

        Returns:
            True if conversion is possible, False otherwise.
        """
        input_fmt = self.input_type.lower()
        output_fmt = self.output_type.lower()

        if input_fmt not in self.supported_input_formats:
            return False
        if output_fmt not in self.supported_output_formats:
            return False

        if input_fmt in _IMAGE_TO_PDF_INPUT_FORMATS:
            return output_fmt == 'pdf'

        return True

    @classmethod
    def get_formats_compatible_with(cls, format_type: str) -> set:
        """
        Get the set of compatible output formats for a given input format.

        Args:
            format_type: The input format to check compatibility for.

        Returns:
            Set of compatible output formats.
        """
        fmt = format_type.lower()
        if fmt not in cls.supported_input_formats:
            return set()
        if fmt in _IMAGE_TO_PDF_INPUT_FORMATS:
            return {'pdf'}
        return cls.supported_output_formats - {fmt}

    def _extract_text(self, doc: fitz.Document) -> str:
        """
        Extract plain text from all pages of the PDF.

        Args:
            doc: An opened PyMuPDF document.

        Returns:
            Extracted text content.
        """
        pages = []
        for page in doc:
            text = page.get_text("text")
            if text.strip():
                pages.append(text)
        return "\n\n".join(pages)

    def _extract_markdown(self) -> str:
        """
        Extract content from the PDF as markdown.

        Uses pymupdf4llm which preserves document structure including
        headings, bold/italic, lists, tables, and code blocks.

        Returns:
            Markdown-formatted content.
        """
        return pymupdf4llm.to_markdown(self.input_file, show_progress=False)

    def _extract_html(self) -> str:
        """
        Extract content from the PDF as HTML.

        Converts via pymupdf4llm markdown extraction, then uses
        PyMuPDF's markdown-to-HTML conversion for structure-preserving output.

        Returns:
            HTML-formatted content.
        """
        md_text = pymupdf4llm.to_markdown(self.input_file, show_progress=False)
        body = markdown.markdown(md_text, extensions=['tables', 'fenced_code'])
        return (
            "<!DOCTYPE html>\n"
            "<html>\n"
            "<head><meta charset=\"utf-8\"></head>\n"
            f"<body>\n{body}\n</body>\n"
            "</html>"
        )

    def convert(self, overwrite: bool = True, quality: Optional[str] = None) -> list[str]:
        """
        Convert the PDF to the output format using PyMuPDF.

        Args:
            overwrite: Whether to overwrite existing output file (default: True)
            quality: For raster output, controls render DPI and encoder
                quality ('low', 'medium', 'high'). Ignored for text outputs.

        Returns:
            List of paths to the converted output file(s). Text outputs
            return a single file. Raster outputs return one file per PDF
            page; the service layer packages multi-page results into a ZIP.

        Raises:
            FileNotFoundError: If input file doesn't exist.
            ValueError: If the conversion is not supported.
            RuntimeError: If conversion fails.
        """
        if not self.can_convert():
            raise ValueError(
                f"Conversion from {self.input_type} to {self.output_type} is not supported."
            )

        if not os.path.isfile(self.input_file):
            raise FileNotFoundError(f"Input file not found: {self.input_file}")

        if self.input_type in _IMAGE_TO_PDF_INPUT_FORMATS:
            return self._convert_image_to_pdf(overwrite)

        if self.output_type == 'pdf':
            return self._convert_pdf_to_pdf(overwrite)

        if self.output_type in _RASTER_OUTPUT_FORMATS:
            return self._convert_to_raster(overwrite, quality)

        # Generate output filename
        input_filename = Path(self.input_file).stem
        output_file = os.path.join(
            self.output_dir, f"{input_filename}.{self.output_type}"
        )

        # Check if output file exists and overwrite is False
        if not overwrite and os.path.exists(output_file):
            return [output_file]

        try:
            doc = fitz.open(self.input_file)

            if self.output_type == 'txt':
                content = self._extract_text(doc)
            elif self.output_type == 'md':
                content = self._extract_markdown()
            elif self.output_type == 'html':
                content = self._extract_html()
            else:
                doc.close()
                raise ValueError(f"Unsupported output format: {self.output_type}")

            doc.close()

            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(content)

            if not os.path.exists(output_file):
                raise RuntimeError(f"Output file was not created: {output_file}")

            return [output_file]

        except (ValueError, RuntimeError):
            raise
        except Exception as e:
            raise RuntimeError(f"PDF extraction failed: {str(e)}")

    def _convert_image_to_pdf(self, overwrite: bool) -> list[str]:
        """Wrap a raster image in a single-page PDF via PyMuPDF."""
        input_filename = Path(self.input_file).stem
        output_file = os.path.join(self.output_dir, f"{input_filename}.pdf")

        if not overwrite and os.path.exists(output_file):
            return [output_file]

        try:
            image = Image.open(self.input_file)
            image.load()
            image = self._prepare_image_for_pdf(image)

            dpi_x, dpi_y = self._get_image_dpi(image)
            width_pt = max(1.0, image.width * 72.0 / dpi_x)
            height_pt = max(1.0, image.height * 72.0 / dpi_y)

            image_buffer = BytesIO()
            image.save(image_buffer, format='PNG')

            doc = fitz.open()
            try:
                page = doc.new_page(width=width_pt, height=height_pt)
                page.insert_image(page.rect, stream=image_buffer.getvalue())
                doc.save(output_file)
            finally:
                doc.close()
        except Exception as exc:
            raise RuntimeError(f"Image to PDF conversion failed: {exc}") from exc

        if not os.path.exists(output_file):
            raise RuntimeError(f"Output file was not created: {output_file}")

        return [output_file]

    def _convert_pdf_to_pdf(self, overwrite: bool) -> list[str]:
        """Rewrite a PDF-family input as a standard PDF output file."""
        input_filename = Path(self.input_file).stem
        output_file = os.path.join(self.output_dir, f"{input_filename}.pdf")

        if not overwrite and os.path.exists(output_file):
            return [output_file]

        if os.path.abspath(self.input_file) == os.path.abspath(output_file):
            return [output_file]

        try:
            with fitz.open(self.input_file) as doc:
                doc.save(output_file)
        except Exception:
            shutil.copy2(self.input_file, output_file)

        if not os.path.exists(output_file):
            raise RuntimeError(f"Output file was not created: {output_file}")

        return [output_file]

    @staticmethod
    def _prepare_image_for_pdf(image: Image.Image) -> Image.Image:
        """Normalize Pillow image state for deterministic PDF embedding."""
        image = image.copy()
        if image.mode == 'P':
            image = image.convert('RGBA')
        return image

    @staticmethod
    def _get_image_dpi(image: Image.Image) -> tuple[float, float]:
        """Return a sane DPI tuple for page sizing."""
        dpi = image.info.get('dpi')
        if isinstance(dpi, tuple) and len(dpi) == 2:
            dpi_x, dpi_y = dpi
        elif isinstance(dpi, (int, float)):
            dpi_x = dpi_y = dpi
        else:
            dpi_x = dpi_y = 72

        dpi_x = float(dpi_x) if dpi_x else 72.0
        dpi_y = float(dpi_y) if dpi_y else 72.0
        return max(dpi_x, 1.0), max(dpi_y, 1.0)

    # ------------------------------------------------------------------
    # Raster rendering (PDF -> image)
    # ------------------------------------------------------------------

    def _convert_to_raster(
        self, overwrite: bool, quality: Optional[str]
    ) -> list[str]:
        """Render every page of the PDF to a raster image file."""
        HeifImagePlugin.register_heif_opener()

        dpi = _RASTER_QUALITY_DPI.get((quality or '').lower(), _DEFAULT_RASTER_DPI)
        save_kwargs = self._get_pillow_save_kwargs(self.output_type, quality)
        pillow_format = _PILLOW_FORMAT_NAMES.get(self.output_type, self.output_type.upper())

        input_filename = Path(self.input_file).stem
        output_paths: list[str] = []

        try:
            doc = fitz.open(self.input_file)
        except Exception as exc:
            raise RuntimeError(f"Failed to open PDF: {exc}") from exc

        try:
            page_count = doc.page_count
            if page_count <= 0:
                raise RuntimeError("PDF contains no pages.")

            # Pad the page index so filenames sort lexicographically.
            pad_width = max(3, len(str(page_count)))

            for page_index in range(page_count):
                page = doc.load_page(page_index)
                page_label = str(page_index + 1).zfill(pad_width)
                output_file = os.path.join(
                    self.output_dir,
                    f"{input_filename}-page-{page_label}.{self.output_type}",
                )

                if not overwrite and os.path.exists(output_file):
                    output_paths.append(output_file)
                    continue

                try:
                    pixmap = page.get_pixmap(dpi=dpi, alpha=True)
                    # Round-trip through Pillow so we get broad format support
                    # and consistent encoder options.
                    image = Image.open(BytesIO(pixmap.tobytes("png")))
                    image = self._prepare_image_for_format(image, self.output_type)
                    image.save(output_file, format=pillow_format, **save_kwargs)
                except Exception as exc:
                    raise RuntimeError(
                        f"Failed to render PDF page {page_index + 1}: {exc}"
                    ) from exc

                if not os.path.exists(output_file):
                    raise RuntimeError(f"Output file was not created: {output_file}")
                output_paths.append(output_file)
        finally:
            doc.close()

        return output_paths

    @staticmethod
    def _prepare_image_for_format(image: Image.Image, output_format: str) -> Image.Image:
        """Convert image mode to one that the target encoder accepts."""
        fmt = output_format.lower()
        # Formats that don't support alpha — flatten on white.
        if fmt in {'jpeg', 'jpg', 'pbm', 'pgm', 'ppm', 'pnm', 'pcx', 'bmp', 'dib', 'pfm'}:
            if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
                background = Image.new('RGB', image.size, (255, 255, 255))
                rgba = image.convert('RGBA')
                background.paste(rgba, mask=rgba.split()[-1])
                return background
            if image.mode != 'RGB':
                return image.convert('RGB')
            return image
        if fmt == 'gif':
            # GIF prefers palette mode.
            return image.convert('RGBA') if image.mode != 'RGBA' else image
        if image.mode == 'P':
            return image.convert('RGBA')
        return image

    @staticmethod
    def _get_pillow_save_kwargs(
        output_format: str, quality: Optional[str]
    ) -> dict:
        """Map quality hints to Pillow encoder options."""
        fmt = output_format.lower()
        q = (quality or '').lower()
        kwargs: dict = {}

        if fmt in ('jpeg', 'jpg'):
            kwargs['quality'] = {'low': 60, 'medium': 80, 'high': 95}.get(q, 85)
            kwargs['optimize'] = True
        elif fmt == 'webp':
            kwargs['quality'] = {'low': 60, 'medium': 80, 'high': 95}.get(q, 80)
        elif fmt == 'avif':
            kwargs['quality'] = {'low': 50, 'medium': 70, 'high': 90}.get(q, 70)
        elif fmt == 'jxl':
            kwargs['quality'] = {'low': 60, 'medium': 80, 'high': 95}.get(q, 80)
        elif fmt == 'jp2':
            kwargs['quality_mode'] = 'rates'
            kwargs['quality_layers'] = {
                'low': [40], 'medium': [20], 'high': [5]
            }.get(q, [10])
        elif fmt == 'tiff':
            kwargs['compression'] = 'tiff_deflate'
        elif fmt == 'png':
            kwargs['optimize'] = True

        return kwargs
