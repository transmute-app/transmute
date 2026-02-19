import subprocess
import os
from pathlib import Path
from typing import Optional
from .converter_interface import ConverterInterface

class FFmpegConverter(ConverterInterface):
    video_formats: set = {
        'mp4', 
        'avi', 
        'mov', 
        'mkv', 
        'webm', 
        'flv', 
        'wmv', 
        'mpg', 
        'mpeg', 
        'm4v', 
        'gif'
      }
    audio_formats: set = {
        'mp3',
        'wav',
        'aac',
        'flac',
        'ogg',
        'wma',
        'm4a',
        'opus'
      }
    supported_input_formats: set = video_formats | audio_formats
    supported_output_formats: set = set(supported_input_formats)

    def __init__(self, input_file: str, output_dir: str, input_type: str, output_type: str):
        """
        Initialize FFmpeg converter.
        
        Args:
            input_file: Path to the input audio/video file
            output_dir: Directory where the converted file will be saved
            input_type: Input file format (e.g., 'mp4', 'avi', 'mp3', 'wav')
            output_type: Output file format (e.g., 'mp4', 'avi', 'mp3', 'wav')
        """
        super().__init__(input_file, output_dir, input_type, output_type)
    
    def __can_convert(self) -> bool:
        """
        Check if the input file can be converted to the output format.
        
        Returns:
            True if conversion is possible, False otherwise
        """
        # Check if formats are supported
        if self.input_type not in self.supported_input_formats or self.output_type not in self.supported_output_formats:
            return False
        
        # Determine input and output categories
        input_is_audio = self.input_type in self.audio_formats
        output_is_video = self.output_type in self.video_formats
        
        # Invalid: Cannot convert audio-only to video format
        # (would need video content, not just audio)
        if input_is_audio and output_is_video:
            return False
        
        # All other conversions are valid:
        # - Video to Video (convert)
        # - Video to Audio (extract audio)
        # - Audio to Audio (convert)
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
        if format_type.lower() in cls.audio_formats:
            # For audio formats, compatible formats are other audio formats
            return cls.audio_formats - {format_type.lower()}
        else:
            return cls.supported_output_formats - {format_type.lower()}
    
    def convert(self, overwrite: bool = True, quality: Optional[str] = None) -> str:
        """
        Convert the input file to the output format using FFmpeg.
        
        Args:
            overwrite: Whether to overwrite existing output file (default: True)
            quality: Optional quality setting for video ('high', 'medium', 'low')
        
        Returns:
            Path to the converted output file
            
        Raises:
            FileNotFoundError: If input file doesn't exist
            ValueError: If the conversion is not supported
            RuntimeError: If FFmpeg conversion fails
        """
        # Validate conversion is possible
        if not self.__can_convert():
            raise ValueError(
                f"Cannot convert {self.input_type} to {self.output_type}. "
                f"Audio-only formats cannot be converted to video formats."
            )
        
        # Check if input file exists
        if not os.path.isfile(self.input_file):
            raise FileNotFoundError(f"Input file not found: {self.input_file}")
        
        # Generate output filename
        input_filename = Path(self.input_file).stem
        output_file = os.path.join(self.output_dir, f"{input_filename}.{self.output_type}")
        
        # Build FFmpeg command
        cmd = ['ffmpeg']
        
        if overwrite:
            cmd.append('-y')
        else:
            cmd.append('-n')
        
        cmd.extend(['-i', self.input_file])
        
        # Add quality settings for video conversions
        if quality and self.output_type in ['mp4', 'avi', 'mov', 'mkv', 'webm']:
            if quality == 'high':
                cmd.extend(['-crf', '18', '-preset', 'slow'])
            elif quality == 'medium':
                cmd.extend(['-crf', '23', '-preset', 'medium'])
            elif quality == 'low':
                cmd.extend(['-crf', '28', '-preset', 'fast'])
        
        cmd.append(output_file)
        
        # Execute FFmpeg command
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            return [output_file]
            
        except subprocess.CalledProcessError as e:
            error_msg = f"FFmpeg conversion failed: {e.stderr}"
            raise RuntimeError(error_msg)
        except FileNotFoundError:
            raise RuntimeError(
                "FFmpeg not found. Please install FFmpeg: "
                "https://ffmpeg.org/download.html"
            )
