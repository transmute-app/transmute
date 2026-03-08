import os
import sys
from pathlib import Path
from typing import Optional
from io import BytesIO
from PIL import Image
from pillow_heif import HeifImagePlugin
import pillow_avif  # noqa: F401 — registers AVIF plugin on import
import pillow_jxl   # noqa: F401 — registers JPEG XL plugin on import
from .converter_interface import ConverterInterface

try:
    if sys.platform == 'darwin':
        # Homebrew installs Cairo to paths not searched by default.
        # Setting DYLD_LIBRARY_PATH before the first ctypes load is enough.
        _brew_lib = '/opt/homebrew/lib' if os.path.exists('/opt/homebrew') else '/usr/local/lib'
        os.environ.setdefault('DYLD_LIBRARY_PATH', '')
        if _brew_lib not in os.environ['DYLD_LIBRARY_PATH']:
            os.environ['DYLD_LIBRARY_PATH'] = f"{_brew_lib}:{os.environ['DYLD_LIBRARY_PATH']}"
    import cairosvg
    _CAIROSVG_AVAILABLE = True
except (ImportError, OSError):
    _CAIROSVG_AVAILABLE = False


class PillowConverter(ConverterInterface):
    supported_input_formats: set = {
        'jpeg',
        'png',
        'gif',
        'bmp',
        'tiff',
        'tif',
        'webp',
        'ico',
        'ppm',
        'pgm',
        'pbm',
        'pcx',
        'heif',
        'heic',
        'svg',
        'tga',
        'jp2',
        'sgi',
        # Extended formats
        'icns',
        'dds',
        'psd',  # read-only
        'blp',
        'cur',  # read-only
        'dcx',
        'fli',
        'flc',
        'xbm',
        'xpm',  # read-only
        'msp',
        'qoi',
        'dib',
        'avif',
        'jxl',
    }
    supported_output_formats: set = {
        'jpeg',
        'png',
        'gif',
        'bmp',
        'tiff',
        'tif',
        'webp',
        'ico',
        'ppm',
        'pgm',
        'pbm',
        'pcx',
        'heif',
        'heic',
        'tga',
        'jp2',
        'sgi',
        'pdf',
        # Extended formats (all writable; psd/cur/xpm are read-only and excluded)
        'icns',
        'dds',
        'blp',
        'dcx',
        'fli',
        'flc',
        'xbm',
        'msp',
        'qoi',
        'dib',
        'avif',
        'jxl',
    }
    def __init__(self, input_file: str, output_dir: str, input_type: str, output_type: str):
        """
        Initialize Pillow converter.
        
        Args:
            input_file: Path to the input image file
            output_dir: Directory where the converted file will be saved
            input_type: Input file format (e.g., 'jpg', 'png', 'bmp')
            output_type: Output file format (e.g., 'jpg', 'png', 'bmp')
        """
        super().__init__(input_file, output_dir, input_type, output_type)
        HeifImagePlugin.register_heif_opener()
    
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
        
        # All supported image format conversions are valid with Pillow
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
        # Can convert FROM SVG but not TO SVG (rasterization only)
        base_formats.discard('svg')
        # Read-only formats cannot be output targets
        for ro_fmt in ('psd', 'cur', 'xpm'):
            base_formats.discard(ro_fmt)
        # SVG input requires cairosvg
        if format_type.lower() == 'svg' and not _CAIROSVG_AVAILABLE:
            return set()
        return base_formats

    
    def convert(self, overwrite: bool = True, quality: Optional[str] = None) -> list[str]:
        """
        Convert the input image file to the output format using Pillow.
        
        Args:
            overwrite: Whether to overwrite existing output file (default: True)
            quality: Quality setting for lossy formats ('high', 'medium', 'low')
        
        Returns:
            List containing the path to the converted output file
            
        Raises:
            FileNotFoundError: If input file doesn't exist
            ValueError: If the conversion is not supported
            RuntimeError: If image conversion fails
        """
        # Validate conversion is possible
        if not self.can_convert():
            raise ValueError(
                f"Cannot convert {self.input_type} to {self.output_type}. "
                f"Unsupported image format."
            )
        
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
            # Handle SVG input specially
            input_fmt = self.input_type.lower()
            if input_fmt == 'svg':
                if not _CAIROSVG_AVAILABLE:
                    raise RuntimeError(
                        "cairosvg is required for SVG conversion but could not be loaded. "
                        "Install Cairo (e.g. `brew install cairo`) and cairosvg (`pip install cairosvg`)."
                    )
                # Convert SVG to PNG with transparency using cairosvg
                png_data = cairosvg.svg2png(url=self.input_file)
                img = Image.open(BytesIO(png_data))
            else:
                # Open the image
                img = Image.open(self.input_file)
            
            # Handle transparency for formats that don't support alpha
            output_fmt = self.output_type.lower()

            # BLP only supports P (palette) mode
            if output_fmt == 'blp' and img.mode != 'P':
                img = img.convert('P')

            _no_alpha_formats = {'jpg', 'jpeg', 'pdf', 'sgi', 'bmp', 'ppm', 'pcx', 'gif', 'tga',
                                    'dib', 'msp', 'xbm', 'fli', 'flc', 'dcx'}
            if output_fmt in _no_alpha_formats and img.mode in ['RGBA', 'LA', 'P']:
                if img.mode == 'P':
                    img = img.convert('RGBA')
                if img.mode in ['RGBA', 'LA']:
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'LA':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1])  # Use alpha channel as mask
                    img = background

            # Set quality parameters
            save_kwargs = {}
            if output_fmt in ['jpg', 'jpeg', 'webp', 'avif', 'jxl']:
                if quality == 'high':
                    save_kwargs['quality'] = 95
                elif quality == 'low':
                    save_kwargs['quality'] = 60
                else:  # medium or None
                    save_kwargs['quality'] = 85

            # JPEG 2000 uses quality_layers instead of quality
            if output_fmt == 'jp2':
                if quality == 'high':
                    save_kwargs['quality_layers'] = [100]
                elif quality == 'low':
                    save_kwargs['quality_layers'] = [30]
                else:
                    save_kwargs['quality_layers'] = [80]

            # For PNG, handle optimization
            if output_fmt == 'png':
                save_kwargs['optimize'] = True

            # Save the image
            img.save(output_file, **save_kwargs)
            
            return [output_file]
            
        except Exception as e:
            error_msg = f"Image conversion failed: {str(e)}"
            raise RuntimeError(error_msg)
