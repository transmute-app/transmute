import os
import logging

from pathlib import Path
from typing import Optional

import ocrmypdf

from .converter_interface import ConverterInterface
from core import media_type_extensions


class OCRmyPDFConverter(ConverterInterface):
    """
    Converter for PDF to PDF/A using OCRmyPDF (which wraps Ghostscript).
    Also adds OCR to scanned PDFs as a side-effect.
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
        'pdf/a',
    }

    def __init__(self, input_file: str, output_dir: str, input_type: str, output_type: str):
        super().__init__(input_file, output_dir, input_type, output_type)

    def can_convert(self) -> bool:
        input_fmt = self.input_type.lower()
        output_fmt = self.output_type.lower()
        return (
            input_fmt in self.supported_input_formats
            and output_fmt in self.supported_output_formats
        )

    @classmethod
    def get_formats_compatible_with(cls, format_type: str) -> set:
        fmt = format_type.lower()
        if fmt not in cls.supported_input_formats:
            return set()
        return cls.supported_output_formats - {fmt}

    def convert(self, overwrite: bool = True, quality: Optional[str] = None) -> list[str]:
        """
        Convert a PDF to PDF/A using ocrmypdf.

        Args:
            overwrite: Whether to overwrite existing output file.
            quality: Not used for this converter.

        Returns:
            List containing the path to the converted PDF/A file.
        """
        if not self.can_convert():
            raise ValueError(
                f"Conversion from {self.input_type} to {self.output_type} is not supported."
            )

        if not os.path.isfile(self.input_file):
            raise FileNotFoundError(f"Input file not found: {self.input_file}")

        input_filename = Path(self.input_file).stem
        output_extension = media_type_extensions.get(self.output_type, self.output_type)
        output_file = os.path.join(self.output_dir, f"{input_filename}.{output_extension}")

        if not overwrite and os.path.exists(output_file):
            return [output_file]

        logging.debug("Running ocrmypdf: %s -> %s", self.input_file, output_file)

        # Suppress ocrmypdf's verbose logging during conversion.
        # Suppress ocrmypdf's verbose logging during conversion.
        # Use the official configure_logging API with Verbosity.quiet so the
        # "ocrmypdf" handler only emits ERROR+, and disable propagation so
        # nothing leaks to uvicorn's root logger.
        ocrmypdf.configure_logging(
            ocrmypdf.Verbosity.quiet,
            progress_bar_friendly=False,
            manage_root_logger=False,
        )
        ocr_logger = logging.getLogger("ocrmypdf")
        ocr_logger.propagate = False

        # pdfminer is "extremely chatty at logging.INFO" per the docs
        pdfminer_logger = logging.getLogger("pdfminer")
        pdfminer_logger.setLevel(logging.ERROR)
        pdfminer_logger.propagate = False

        try:
            ocrmypdf.ocr(
                self.input_file,
                output_file,
                output_type="pdfa",
                skip_text=True,
                progress_bar=False,
            )
        except ocrmypdf.exceptions.PriorOcrFoundError:
            ocrmypdf.ocr(
                self.input_file,
                output_file,
                output_type="pdfa",
                force_ocr=True,
                progress_bar=False,
            )
        except ocrmypdf.exceptions.OcrmypdfError as exc:
            raise RuntimeError(f"ocrmypdf conversion failed: {exc}") from exc

        if not os.path.exists(output_file):
            raise RuntimeError(f"Output file was not created: {output_file}")

        return [output_file]
