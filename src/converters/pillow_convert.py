import os
from pathlib import Path
from typing import Optional
from PIL import Image
from .converter_interface import ConverterInterface

class PillowConverter(ConverterInterface):
    supported_formats = {
        'jpg', 
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
        'pcx'
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
    
    def __can_convert(self) -> bool:
        """
        Check if the input file can be converted to the output format.
        
        Returns:
            True if conversion is possible, False otherwise
        """
        input_fmt = self.input_type.lower()
        output_fmt = self.output_type.lower()
        
        # Check if formats are supported
        if input_fmt not in self.supported_formats or output_fmt not in self.supported_formats:
            return False
        
        # All supported image format conversions are valid with Pillow
        return True
    
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
        if not self.__can_convert():
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
            # Open the image
            img = Image.open(self.input_file)
            
            # Handle transparency for formats that don't support it
            output_fmt = self.output_type.lower()
            if output_fmt in ['jpg', 'jpeg'] and img.mode in ['RGBA', 'LA', 'P']:
                # Convert RGBA to RGB for JPEG (add white background)
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
            if output_fmt in ['jpg', 'jpeg', 'webp']:
                if quality == 'high':
                    save_kwargs['quality'] = 95
                elif quality == 'low':
                    save_kwargs['quality'] = 60
                else:  # medium or None
                    save_kwargs['quality'] = 85
            
            # For PNG, handle optimization
            if output_fmt == 'png':
                save_kwargs['optimize'] = True
            
            # Save the image
            img.save(output_file, **save_kwargs)
            
            return [output_file]
            
        except Exception as e:
            error_msg = f"Image conversion failed: {str(e)}"
            raise RuntimeError(error_msg)
