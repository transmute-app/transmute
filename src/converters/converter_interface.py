import os
from typing import Optional

class ConverterInterface:
    supported_formats: set = set()  # To be defined by subclasses with supported formats

    def __init__(self, input_file: str, output_dir: str, input_type: str, output_type: str):
        """
        Initialize converter interface.
        
        Args:
            input_file: Path to the input file
            output_dir: Directory where the output file will be saved
            input_type: Format of the input file (e.g., "mp4", "mp3")
            output_type: Format of the output file (e.g., "mp4", "mp3")
        """
        self.input_file = input_file
        self.output_dir = output_dir
        self.input_type = input_type
        self.output_type = output_type
        
        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
        
    
    def __can_convert(self) -> bool:
        """
        Check if conversion between the specified formats is possible.
        
        Returns:
            True if conversion is possible, False otherwise.
        """
        raise NotImplementedError("can_convert method must be implemented by subclasses.")
    
    @classmethod
    def get_formats_compatible_with(cls, format_type: str) -> set:
        """
        Get the set of compatible formats for conversion.
        
        Args:
            format_type: The input format to check compatibility for.
        
        Returns:
            Set of compatible formats.
        """
        return cls.supported_formats - {format_type.lower()}
    
    def convert(self, overwrite: bool = True, quality: Optional[str] = None) -> list[str]:
        """
        Convert the input file to the output format.
        
        Args:
            overwrite: Whether to overwrite existing output file (default: True)
            quality: Quality setting for conversion (e.g., "high", "medium", "low")
        
        Returns:
            List of paths to the converted output files.
        """
        raise NotImplementedError("convert method must be implemented by subclasses.")