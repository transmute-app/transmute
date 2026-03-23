import os
import subprocess  # nosec B404
import sys
from pathlib import Path
from typing import Optional

from core import validate_safe_path

from .converter_interface import ConverterInterface

class CalibreConverter(ConverterInterface):
    supported_input_formats = {
        'epub',
        'mobi',
        'pdf',
        'pdf/a',
        'pdf/x',
        'pdf/e',
        'pdf/ua',
        'pdf/vt',
        'azw3',
        'lrf',
        'fb2',
        'pdb',
    }
    supported_output_formats = {
        'epub',
        'mobi',
        'pdf',
        'azw3',
        'lrf',
        'fb2',
        'pdb',
        'snb',
    }
    calibre_paths = {
        'darwin': '/Applications/calibre.app/Contents/MacOS/ebook-convert',
        'linux': '/usr/bin/ebook-convert',
        'win32': 'C:\\Program Files\\Calibre2\\ebook-convert.exe',
    }
    calibre_path = calibre_paths.get(sys.platform, 'ebook-convert')
    
    def __init__(self, input_file: str, output_dir: str, input_type: str, output_type: str):
        """
        Initialize Calibre converter.
        
        Args:
            input_file: Path to the input ebook file
            output_dir: Directory where the converted file will be saved
            input_type: Input file format (e.g., 'epub', 'mobi', 'pdf')
            output_type: Output file format (e.g., 'epub', 'mobi', 'pdf')
        """
        super().__init__(input_file, output_dir, input_type, output_type)
    
    @classmethod
    def can_register(cls) -> bool:
        """
        Check if the Calibre converter can be registered.
        
        Returns:
            True if Calibre is available, False otherwise.
        """
        try:
            # Subprocess is safe here because the command is constructed without
            # user input.
            subprocess.run([cls.calibre_path, '--version'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # nosec B603
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def can_convert(self) -> bool:
        """
        Check if the input file can be converted to the output format.
        
        Returns:
            True if conversion is possible, False otherwise
        """
        input_fmt = self.input_type.lower()
        output_fmt = self.output_type.lower()
        
        # Check if formats are supported
        if input_fmt not in self.supported_input_formats or output_fmt not in self.supported_output_formats:
            return False
        
        return True

    @classmethod
    def get_formats_compatible_with(cls, format_type: str) -> set:
        """
        Get the set of compatible formats for conversion.
        
        Args:
            format_type: The input format to check compatibility for.
        Returns:
            Set of compatible formats.
        """
        normalized_format = format_type.lower()
        if normalized_format not in cls.supported_input_formats:
            return set()

        return cls.supported_output_formats - {normalized_format}
    
    def convert(self, overwrite: bool = True, quality: Optional[str] = None) -> list[str]:
        """
        Convert the ebook file to the output format using Calibre CLI directly.
        
        Args:
            overwrite: Whether to overwrite existing output file (default: True)
            quality: Quality setting (not used for Calibre conversion)
        
        Returns:
            List containing the path to the converted output file
            
        Raises:
            FileNotFoundError: If input file doesn't exist or Calibre not installed
            ValueError: If the conversion is not supported
            RuntimeError: If conversion fails
        """
        if not self.can_convert():
            raise ValueError(f"Conversion from {self.input_type} to {self.output_type} is not supported.")
        
        # Check if input file exists
        if not os.path.isfile(self.input_file):
            raise FileNotFoundError(f"Input file not found: {self.input_file}")
        
        # Generate output filename
        input_filename = Path(self.input_file).stem
        output_file = os.path.join(self.output_dir, f"{input_filename}.{self.output_type}")
        
        # Check if output file exists and overwrite is False
        if not overwrite and os.path.exists(output_file):
            return [output_file]
        
        try:
            # Validate input file path
            validate_safe_path(self.input_file)
            validate_safe_path(output_file)

            # Build the Calibre CLI command
            cmd = [
                self.calibre_path,
                self.input_file,  # Input file
                output_file,      # Output file
            ]
            
            # Run the conversion
            # Subprocess is safe here because the input file path is validated
            # and the command is constructed without user input.
            result = subprocess.run( # nosec B603
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=30  # 30 second timeout to prevent hanging
            )
            
            # Verify output file was created
            if not os.path.exists(output_file):
                raise RuntimeError(
                    f"Output file was not created: {output_file}\n"
                    f"Command: {' '.join(cmd)}\n"
                    f"Stdout: {result.stdout}\n"
                    f"Stderr: {result.stderr}"
                )
            
            return [output_file]
            
        except subprocess.CalledProcessError as e:
            error_msg = f"Calibre conversion failed: {e.stderr or e.stdout or str(e)}"
            raise RuntimeError(error_msg)
        except Exception as e:
            error_msg = f"Calibre conversion failed: {str(e)}"
            raise RuntimeError(error_msg)
