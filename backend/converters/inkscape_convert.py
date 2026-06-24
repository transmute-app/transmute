import os
import subprocess  # nosec B404
import sys
from pathlib import Path
from typing import Optional

from core import validate_safe_path

from .converter_interface import ConverterInterface


class VectorConverter(ConverterInterface):
    """Converts between vector formats (SVG, EPS) using Inkscape and Ghostscript."""

    supported_input_formats: set = {
        'svg',
        'eps',
        'svgz',
        'wmf',
        'emf',
        'pdf',
    }
    supported_output_formats: set = {
        'svg',
        'eps',
        'svgz',
        'wmf',
        'emf',
        'pdf',
        'tex',
        'odg',
    }

    # Inkscape only works on Linux in headless mode, and the CLI binary is at a 
    # known path. On other platforms, we can't reliably detect or use Inkscape 
    # headlessly, so we disable this converter entirely.
    inkscape_paths = {
        'linux': '/usr/bin/inkscape',
    }
    inkscape_path = inkscape_paths.get(sys.platform, 'inkscape')

    def __init__(self, input_file: str, output_dir: str, input_type: str, output_type: str):
        super().__init__(input_file, output_dir, input_type, output_type)

    @classmethod
    def can_register(cls) -> bool:
        if sys.platform not in cls.inkscape_paths:
            return False
        try:
            subprocess.run(  # nosec B603
                [cls.inkscape_path, '--version'],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def can_convert(self) -> bool:
        input_fmt = self.input_type.lower()
        output_fmt = self.output_type.lower()

        if input_fmt not in self.supported_input_formats:
            return False
        if output_fmt not in self.supported_output_formats:
            return False
        if input_fmt == output_fmt:
            return False

        return True

    @classmethod
    def get_formats_compatible_with(cls, format_type: str) -> set:
        base_formats = super().get_formats_compatible_with(format_type)
        # Only accept vector inputs this converter knows about
        if format_type.lower() not in cls.supported_input_formats:
            return set()
        return base_formats

    def convert(self, overwrite: bool = True, quality: Optional[str] = None) -> list[str]:
        """
        Convert between vector formats using Inkscape.

        Args:
            overwrite: Whether to overwrite existing output file (default: True)
            quality: Optional DPI hint — 'high' (300), 'medium' (150), 'low' (72).
                     Only relevant when the output is a raster format (png).

        Returns:
            List containing the path to the converted output file.

        Raises:
            FileNotFoundError: If input file doesn't exist.
            ValueError: If the conversion is not supported.
            RuntimeError: If the conversion fails.
        """
        if not self.can_convert():
            raise ValueError(
                f"Conversion from {self.input_type} to {self.output_type} is not supported."
            )

        if not os.path.isfile(self.input_file):
            raise FileNotFoundError(f"Input file not found: {self.input_file}")

        input_filename = Path(self.input_file).stem
        output_file = os.path.join(self.output_dir, f"{input_filename}.{self.output_type}")

        if not overwrite and os.path.exists(output_file):
            return [output_file]

        validate_safe_path(self.input_file)
        validate_safe_path(output_file)

        try:
            output_fmt = self.output_type.lower()

            cmd = [
                self.inkscape_path,
                '--export-filename', output_file,
            ]

            # SVG output needs --export-plain-svg to force headless export
            # mode; other formats use --export-type which is also headless.
            if output_fmt == 'svg':
                cmd.append('--export-plain-svg')
            else:
                cmd.extend(['--export-type', output_fmt])

            # Input file must come last
            cmd.append(self.input_file)

            result = subprocess.run(  # nosec B603
                cmd,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                check=True,
                timeout=60,
                start_new_session=True,
            )

            if not os.path.exists(output_file):
                raise RuntimeError(
                    f"Output file was not created: {output_file}\n"
                    f"Stdout: {result.stdout}\n"
                    f"Stderr: {result.stderr}"
                )

            return [output_file]

        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Inkscape conversion failed: {e.stderr or e.stdout or str(e)}"
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("Inkscape conversion timed out after 60 seconds.")
