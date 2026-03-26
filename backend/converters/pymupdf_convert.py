import os
import fitz  # PyMuPDF
import pymupdf4llm
import markdown
from pathlib import Path
from typing import Optional

from .converter_interface import ConverterInterface


class PyMuPDFConverter(ConverterInterface):
    """
    Converter for extracting content from PDF files using PyMuPDF.
    Supports converting PDFs to text, markdown, and HTML formats.
    """

    supported_input_formats: set = {
        'pdf',
        'pdf/a',
        'pdf/x',
        'pdf/e',
        'pdf/ua',
        'pdf/vt',
    }
    supported_output_formats: set = {
        'txt',
        'md',
        'html',
    }

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
            quality: Not applicable for PDF text extraction, ignored.

        Returns:
            List containing the path to the converted output file.

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
