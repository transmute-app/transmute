import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from .converter_interface import ConverterInterface

class DrawioConverter(ConverterInterface):
    supported_input_formats = {
        'drawio'
    }
    supported_output_formats = {
        'png',
        'pdf',
        'svg',
        'jpeg',
    }
    
    # Draw.io CLI path by platform
    DRAWIO_PATHS = {
        'darwin': '/Applications/draw.io.app/Contents/MacOS/draw.io',
        'linux': '/opt/drawio/drawio',
        'win32': 'C:\\Program Files\\draw.io\\draw.io.exe',
    }
    
    def __init__(self, input_file: str, output_dir: str, input_type: str, output_type: str):
        """
        Initialize Drawio converter.
        
        Args:
            input_file: Path to the input draw.io file
            output_dir: Directory where the converted file will be saved
            input_type: Input file format (must be 'drawio')
            output_type: Output file format (e.g., 'png', 'pdf', 'svg', 'jpeg')
        """
        super().__init__(input_file, output_dir, input_type, output_type)
    
    def __can_convert(self) -> bool:
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
        
        # Can only convert FROM drawio to other formats
        if input_fmt != 'drawio':
            return False
            
        # Cannot convert drawio to drawio
        if output_fmt == 'drawio':
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
        base_formats = super().get_formats_compatible_with(format_type)
        # Can convert FROM drawio but not TO drawio (export only)
        base_formats.discard('drawio')
        return base_formats
    
    def convert(self, overwrite: bool = True, quality: Optional[str] = None) -> list[str]:
        """
        Convert the draw.io file to the output format using Draw.io CLI directly.
        
        Args:
            overwrite: Whether to overwrite existing output file (default: True)
            quality: Quality setting (not used for drawio conversion)
        
        Returns:
            List containing the path to the converted output file
            
        Raises:
            FileNotFoundError: If input file doesn't exist or Draw.io not installed
            ValueError: If the conversion is not supported
            RuntimeError: If conversion fails
        """
        if not self.__can_convert():
            raise ValueError(f"Conversion from {self.input_type} to {self.output_type} is not supported.")
        
        # Check if input file exists
        if not os.path.isfile(self.input_file):
            raise FileNotFoundError(f"Input file not found: {self.input_file}")
        
        # Get Draw.io executable path for current platform
        drawio_path = self.DRAWIO_PATHS.get(sys.platform)
        if not drawio_path or not os.path.exists(drawio_path):
            raise FileNotFoundError(
                f"Draw.io application not found at {drawio_path}. "
                "Please install Draw.io from https://www.drawio.com/"
            )
        
        # Generate output filename
        input_filename = Path(self.input_file).stem
        output_file = os.path.join(self.output_dir, f"{input_filename}.{self.output_type}")
        
        # Check if output file exists and overwrite is False
        if not overwrite and os.path.exists(output_file):
            return [output_file]
        
        try:
            # Build the Draw.io CLI command
            # -x: export mode
            # -p: page index (0 for first page)
            # -o: output file
            # --transparent: transparent background for PNG
            cmd = [
                drawio_path,
                '-x',
                self.input_file,
                '-p', '0',  # Export first page
                '-o', output_file,
            ]
            
            # Add transparency for PNG format
            if self.output_type.lower() == 'png':
                cmd.append('--transparent')
            
            # Run the conversion
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
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
            error_msg = f"Drawio conversion failed: {e.stderr or e.stdout or str(e)}"
            raise RuntimeError(error_msg)
        except Exception as e:
            error_msg = f"Drawio conversion failed: {str(e)}"
            raise RuntimeError(error_msg)
