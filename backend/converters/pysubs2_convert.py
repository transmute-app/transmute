import os
import pysubs2
from pathlib import Path
from typing import Optional
from pysubs2.exceptions import UnknownFPSError

from .converter_interface import ConverterInterface


class PySubs2Converter(ConverterInterface):
    """
    Converter for subtitle formats using pysubs2.
    Supports conversions between ASS, SSA, SRT, MicroDVD, MPL2, etc.
    """

    # Mapping from our format names to pysubs2 format identifiers
    _pysubs2_format_map = {
        'ass': 'ass',
        'ssa': 'ssa',
        'srt': 'srt',
        'sub': 'microdvd',
        'mpl': 'mpl2',
        'tmp': 'tmp',
        'vtt': 'vtt',
    }

    supported_input_formats: set = set(_pysubs2_format_map.keys())
    supported_output_formats: set = set(_pysubs2_format_map.keys())
    _default_microdvd_fps = 24

    def __init__(self, input_file: str, output_dir: str, input_type: str, output_type: str):
        """
        Initialize pysubs2 converter.

        Args:
            input_file: Path to the input subtitle file
            output_dir: Directory where the converted file will be saved
            input_type: Input file format (e.g., 'srt', 'ass', 'vtt')
            output_type: Output file format (e.g., 'srt', 'ass', 'vtt')
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

    def _load_subtitles(self):
        try:
            return pysubs2.load(self.input_file)
        except UnknownFPSError:
            if self.input_type.lower() != 'sub':
                raise
            return pysubs2.load(self.input_file, fps=self._default_microdvd_fps)

    def convert(self, overwrite: bool = True, quality: Optional[str] = None) -> list[str]:
        """
        Convert the input subtitle file to the output format using pysubs2.

        Args:
            overwrite: Whether to overwrite existing output file (default: True)
            quality: Not applicable for subtitle formats, ignored.

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
            # Load the subtitle file
            subs = self._load_subtitles()

            # Get the pysubs2 format identifier for the output
            output_format = self._pysubs2_format_map.get(self.output_type.lower())
            if not output_format:
                raise ValueError(f"Unsupported output format: {self.output_type}")

            # Save in the target format
            # MicroDVD (.sub) requires an fps value for timing; default to 24.
            if output_format == 'microdvd':
                subs.save(output_file, format_=output_format, fps=self._default_microdvd_fps)
            else:
                subs.save(output_file, format_=output_format)

            if not os.path.exists(output_file):
                raise RuntimeError(f"Output file was not created: {output_file}")

            return [output_file]

        except (ValueError, RuntimeError):
            raise
        except Exception as e:
            raise RuntimeError(f"Subtitle conversion failed: {str(e)}")
