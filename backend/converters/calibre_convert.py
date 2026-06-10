import os
import shutil
import subprocess  # nosec B404
import sys
import uuid
from pathlib import Path
from typing import Optional

from core import get_file_extension, validate_safe_path

from .converter_interface import ConverterInterface

class CalibreConverter(ConverterInterface):
    supported_input_formats = {
        'epub',
        'kepub',
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
        'kepub',
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
        input_fmt = self.requested_input_type.lower()
        output_fmt = self.requested_output_type.lower()
        
        # Check if formats are supported
        if input_fmt not in self.supported_input_formats or output_fmt not in self.supported_output_formats:
            return False

        if input_fmt.startswith('pdf') and output_fmt == 'pdf':
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

        if normalized_format.startswith('pdf'):
            return cls.supported_output_formats - {'pdf', normalized_format}

        return cls.supported_output_formats - {normalized_format}

    @staticmethod
    def _get_input_stem(input_file: str) -> str:
        filename = Path(input_file).name
        extension = get_file_extension(filename)
        if extension:
            suffix = f'.{extension}'
            if filename.lower().endswith(suffix):
                return filename[:-len(suffix)]
        return Path(input_file).stem

    def _get_output_file(self) -> str:
        input_stem = self._get_input_stem(self.input_file)
        output_extension = 'kepub.epub' if self.requested_output_type.lower() == 'kepub' else self.output_type
        return os.path.join(self.output_dir, f"{input_stem}.{output_extension}")

    def _prepare_input_file(self) -> tuple[str, Optional[str]]:
        if self.requested_input_type.lower() != 'kepub':
            return self.input_file, None

        staged_input = Path(self.input_file).parent / f"{uuid.uuid4().hex}.epub"
        shutil.copy2(self.input_file, staged_input)
        return str(staged_input), str(staged_input)
    
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
        output_file = self._get_output_file()
        
        # Check if output file exists and overwrite is False
        if not overwrite and os.path.exists(output_file):
            return [output_file]
        
        staged_input_to_cleanup = None
        try:
            command_input_file, staged_input_to_cleanup = self._prepare_input_file()

            # Validate input file path
            validate_safe_path(self.input_file)
            if staged_input_to_cleanup is not None:
                validate_safe_path(command_input_file)
            validate_safe_path(output_file)

            # Build the Calibre CLI command
            cmd = [
                self.calibre_path,
                command_input_file,  # Input file
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
        finally:
            if staged_input_to_cleanup is not None:
                try:
                    os.remove(staged_input_to_cleanup)
                except FileNotFoundError:
                    pass
