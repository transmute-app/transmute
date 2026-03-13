import os
import pypandoc
from pathlib import Path
from typing import Optional

from .converter_interface import ConverterInterface


class PyPandocConverter(ConverterInterface):
    """
    Converter for document formats using pypandoc (a Python wrapper for Pandoc).
    Supports conversions between markdown, HTML, plain text, Word documents,
    reStructuredText, LaTeX, EPUB, and other document formats.
    """

    supported_input_formats: set = {
        'md',
        'html',
        'txt',
        'docx',
        'rst',
        'latex',
        'tex',
        'epub',
        'odt',
        'rtf',
        'org',
        'textile',
        'mediawiki',
        'adoc',
        'ipynb',
        'fb2',
        'muse',
        'opml',
        'dbk',
    }
    supported_output_formats: set = {
        'md',
        'html',
        'txt',
        'docx',
        'rst',
        'latex',
        'tex',
        'epub',
        'odt',
        'rtf',
        'org',
        'adoc',
        'pdf',
        'ipynb',
        'textile',
        'mediawiki',
        'pptx',
        'dbk',
        'jira',
        'muse',
        'opml',
    }

    # PDF engine to use for PDF output (weasyprint is installed as a Python
    # dependency and its system libraries are included in the Docker image).
    _pdf_engine = 'weasyprint'

    # Mapping from our format names to Pandoc format identifiers
    _pandoc_format_map = {
        'md': 'gfm',
        'html': 'html',
        'txt': 'plain',
        'docx': 'docx',
        'rst': 'rst',
        'latex': 'latex',
        'tex': 'latex',
        'epub': 'epub',
        'odt': 'odt',
        'rtf': 'rtf',
        'org': 'org',
        'textile': 'textile',
        'mediawiki': 'mediawiki',
        'adoc': 'asciidoc',
        'pdf': 'pdf',
        'ipynb': 'ipynb',
        'fb2': 'fb2',
        'muse': 'muse',
        'opml': 'opml',
        'dbk': 'docbook',
        'pptx': 'pptx',
        'jira': 'jira',
    }

    def __init__(self, input_file: str, output_dir: str, input_type: str, output_type: str):
        """
        Initialize PyPandoc converter.

        Args:
            input_file: Path to the input document file
            output_dir: Directory where the converted file will be saved
            input_type: Input file format (e.g., 'md', 'docx', 'html')
            output_type: Output file format (e.g., 'md', 'docx', 'html')
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
        formats = cls.supported_output_formats - {fmt}
        return formats

    def _get_pandoc_format(self, fmt: str) -> str:
        """
        Map our format name to a Pandoc format identifier.

        Args:
            fmt: Our internal format name.

        Returns:
            The Pandoc format string.
        """
        return self._pandoc_format_map.get(fmt.lower(), fmt.lower())

    def convert(self, overwrite: bool = True, quality: Optional[str] = None) -> list[str]:
        """
        Convert the input document to the output format using pypandoc.

        Args:
            overwrite: Whether to overwrite existing output file (default: True)
            quality: Not applicable for document formats, ignored.

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
            input_pandoc_fmt = self._get_pandoc_format(self.input_type)
            output_pandoc_fmt = self._get_pandoc_format(self.output_type)

            # Extra args for specific output formats
            extra_args = []
            if self.output_type.lower() == 'pdf':
                extra_args.append(f'--pdf-engine={self._pdf_engine}')
            if self.output_type.lower() in ('html', 'revealjs', 'slidy', 's5', 'dzslides'):
                extra_args.append('--standalone')

            pypandoc.convert_file(
                self.input_file,
                output_pandoc_fmt,
                format=input_pandoc_fmt,
                outputfile=output_file,
                extra_args=extra_args if extra_args else [],
            )

            if not os.path.exists(output_file):
                raise RuntimeError(
                    f"Output file was not created: {output_file}"
                )

            return [output_file]

        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Document conversion failed: {str(e)}")