import subprocess  # nosec B404
import sys
import os
import math
import json

from pathlib import Path
from typing import Optional
from .converter_interface import ConverterInterface
from core import validate_safe_path

class FFmpegConverter(ConverterInterface):
    video_formats: set = {
        'mp4',
        'avi',
        'mov',
        'mkv',
        'webm',
        'flv',
        'wmv',
        'mpeg',
        'm4v',
        'gif',
        'apng',
        'ts',
        '3gp',
        'ogv',
        'asf',
        'f4v',
        'fli',
        'flc',
    }
    # Formats FFmpeg can decode but not encode
    _decode_only_formats: set = {
        'fli',
        'flc',
    }
    audio_formats: set = {
        'mp3',
        'wav',
        'aac',
        'flac',
        # 'ogg' excluded: ambiguous container (can be audio or video), use oga for
        # audio-only OGG or ogv for OGG video instead
        'wma',
        'm4a',
        'opus',
        'aiff',
        'mp2',
        'ac3',
        # 'amr' excluded: requires libopencore-amrnb which is not compiled
        # into standard FFmpeg builds (encoder amr_nb unavailable)
        'oga',
        'mka',
    }
    supported_input_formats: set = video_formats | audio_formats
    supported_output_formats: set = (video_formats | audio_formats) - _decode_only_formats

    ffmpeg_paths = {
        'darwin': '/opt/homebrew/bin/ffmpeg',
        'linux': '/usr/bin/ffmpeg',
        'win32': 'C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe',
    }
    ffprobe_paths = {
        'darwin': '/opt/homebrew/bin/ffprobe',
        'linux': '/usr/bin/ffprobe',
        'win32': 'C:\\Program Files\\ffmpeg\\bin\\ffprobe.exe',
    }
    ffmpeg_path = ffmpeg_paths.get(sys.platform, 'ffmpeg')
    ffprobe_path = ffprobe_paths.get(sys.platform, 'ffprobe')
    min_timeout_seconds = 30
    timeout_seconds_per_mb = 2
    max_timeout_seconds = 3600

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
    
    @classmethod
    def can_register(cls) -> bool:
        """
        Check if FFmpeg is available for registration.
        
        Returns:
            True if FFmpeg is available, False otherwise.
        """
        try:
            # Subprocess is safe here because the command is constructed without
            # user input.
            subprocess.run([cls.ffmpeg_path, '-version'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # nosec B603
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def can_convert(self) -> bool:
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
        
        # Animated image formats contain no audio stream.
        # Extracting audio from them is not possible.
        _animated_image_only_formats = {'apng', 'gif', 'fli', 'flc'}
        if self.input_type in _animated_image_only_formats and self.output_type in self.audio_formats:
            return False
        
        # All other conversions are valid:
        # - Video to Video (convert)
        # - Video to Audio (extract audio)
        # - Audio to Audio (convert)
        return True

    def get_size_based_timeout_seconds(self) -> int:
        """Estimate a conversion timeout from input file size."""
        input_size_bytes = Path(self.input_file).stat().st_size
        input_size_mb = max(1, math.ceil(input_size_bytes / (1024 * 1024)))
        timeout_seconds = self.min_timeout_seconds + (input_size_mb * self.timeout_seconds_per_mb)
        return min(timeout_seconds, self.max_timeout_seconds)

    def get_media_probe_data(self) -> dict | None:
        """Return ffprobe metadata for timeout estimation.

        Timeout estimation should not fail conversions just because ffprobe is
        unavailable or a particular file cannot be probed, so this method
        returns ``None`` on probe failure and lets the caller fall back to a
        size-based heuristic.
        """
        validate_safe_path(self.input_file)
        try:
            result = subprocess.run(  # nosec B603
                [
                    self.ffprobe_path,
                    '-v', 'error',
                    '-print_format', 'json',
                    '-show_format',
                    '-show_streams',
                    self.input_file,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
                timeout=10,
            )
            return json.loads(result.stdout)
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            FileNotFoundError,
            json.JSONDecodeError,
        ):
            return None

    @staticmethod
    def get_probe_duration_seconds(probe_data: dict) -> float:
        """Extract media duration from ffprobe output."""
        format_info = probe_data.get('format', {})
        duration = format_info.get('duration')
        if duration is not None:
            try:
                return max(0.0, float(duration))
            except (TypeError, ValueError):
                pass

        stream_durations = []
        for stream in probe_data.get('streams', []):
            stream_duration = stream.get('duration')
            if stream_duration is None:
                continue
            try:
                stream_durations.append(float(stream_duration))
            except (TypeError, ValueError):
                continue
        return max(stream_durations, default=0.0)

    @staticmethod
    def get_video_resolution_factor(probe_data: dict) -> float:
        """Estimate the transcode cost multiplier from the largest video stream."""
        max_pixels = 0
        for stream in probe_data.get('streams', []):
            if stream.get('codec_type') != 'video':
                continue
            width = stream.get('width') or 0
            height = stream.get('height') or 0
            if isinstance(width, int) and isinstance(height, int):
                max_pixels = max(max_pixels, width * height)

        if max_pixels <= 0:
            return 1.0

        baseline_pixels = 1280 * 720
        return min(max(1.0, math.sqrt(max_pixels / baseline_pixels)), 3.0)

    def get_media_based_timeout_seconds(self, quality: Optional[str] = None) -> int | None:
        """Estimate timeout from media duration and stream characteristics."""
        probe_data = self.get_media_probe_data()
        if probe_data is None:
            return None

        duration_seconds = self.get_probe_duration_seconds(probe_data)
        if duration_seconds <= 0:
            return None

        has_video_stream = any(
            stream.get('codec_type') == 'video'
            for stream in probe_data.get('streams', [])
        )

        if not has_video_stream:
            seconds_per_second = 0.4
        elif self.output_type in self.audio_formats:
            seconds_per_second = 0.75
        else:
            seconds_per_second = 1.0 * self.get_video_resolution_factor(probe_data)
            if quality == 'high':
                seconds_per_second *= 1.35
            elif quality == 'low':
                seconds_per_second *= 0.85

        timeout_seconds = self.min_timeout_seconds + math.ceil(duration_seconds * seconds_per_second)
        return min(timeout_seconds, self.max_timeout_seconds)

    def get_conversion_timeout_seconds(self, quality: Optional[str] = None) -> int:
        """Estimate a conversion timeout from media metadata with size fallback."""
        size_based_timeout = self.get_size_based_timeout_seconds()
        media_based_timeout = self.get_media_based_timeout_seconds(quality)
        if media_based_timeout is None:
            return size_based_timeout
        return max(size_based_timeout, media_based_timeout)
    
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
        _animated_image_only_formats = {'apng', 'gif', 'fli', 'flc'}
        if format_type.lower() in _animated_image_only_formats:
            # Animated images have no audio stream — only video targets
            return (cls.video_formats - cls._decode_only_formats - {format_type.lower()})
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
        if not self.can_convert():
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
        cmd = [self.ffmpeg_path]
        
        if overwrite:
            cmd.append('-y')
        else:
            cmd.append('-n')
        
        validate_safe_path(self.input_file)
        cmd.extend(['-i', self.input_file])
        
        # When the output is an audio-only format, strip any video stream.
        # This prevents FFmpeg from attempting to encode video with a codec that
        # may not be available (e.g. theora for ogg, amr_nb for amr).
        if self.output_type in self.audio_formats:
            cmd.append('-vn')

        # Add quality settings for video conversions
        _quality_video_formats = {'mp4', 'avi', 'mov', 'mkv', 'webm', 'ts', '3gp', 'ogv', 'f4v'}
        if quality and self.output_type in _quality_video_formats:
            if quality == 'high':
                cmd.extend(['-crf', '18', '-preset', 'slow'])
            elif quality == 'medium':
                cmd.extend(['-crf', '23', '-preset', 'medium'])
            elif quality == 'low':
                cmd.extend(['-crf', '28', '-preset', 'fast'])

        # Animated image formats encode every frame as a full image.  Without
        # constraints a long or high-resolution video produces enormous output
        # and takes extremely long.  Cap the frame rate and resolution so the
        # conversion stays practical.
        _animated_image_formats = {'apng', 'gif', 'fli', 'flc'}
        if self.output_type in _animated_image_formats and self.input_type not in _animated_image_formats:
            cmd.extend(['-vf', 'fps=10,scale=320:-1:flags=lanczos', '-plays', '0'])

        # FLI/FLC files can have non-standard framerates (e.g. 14 fps) that
        # strict codecs like mpeg1video reject.  Force 25 fps output which is
        # universally accepted by all video codecs.
        _flic_formats = {'fli', 'flc'}
        if self.input_type in _flic_formats:
            cmd.extend(['-r', '25'])

        # Most video codecs/containers cannot handle RGBA input (e.g. from
        # APNG).  Force yuv420p so the alpha channel is stripped before encoding.
        # Animated image outputs that natively support transparency are excluded.
        _alpha_safe_formats = {'apng', 'gif'}
        if self.output_type in (self.video_formats - _alpha_safe_formats):
            cmd.extend(['-pix_fmt', 'yuv420p'])

        # 3GP/3G2 default to H.263 video (limited to specific small resolutions)
        # and amr_nb audio (requires libopencore-amrnb, not in standard FFmpeg builds).
        # Force H.264 + AAC instead, which modern 3GP (3GPP Release 5+) fully supports.
        _mobile_container_formats = {'3gp', '3g2'}
        if self.output_type in _mobile_container_formats:
            cmd.extend(['-c:v', 'libx264', '-c:a', 'aac'])

        cmd.append(output_file)
        timeout_seconds = self.get_conversion_timeout_seconds(quality)
        
        # Execute FFmpeg command
        try:
            # Subprocess is safe here because the input file path is validated
            # and the command is constructed without user input.
            result = subprocess.run( # nosec B603
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
                timeout=timeout_seconds,
            )
            return [output_file]
            
        except subprocess.CalledProcessError as e:
            error_msg = f"FFmpeg conversion failed: {e.stderr}"
            raise RuntimeError(error_msg)
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"FFmpeg conversion timed out after {timeout_seconds} seconds. "
                "Try a smaller file or a faster conversion target."
            )
        except FileNotFoundError:
            raise RuntimeError(
                "FFmpeg not found. Please install FFmpeg: "
                "https://ffmpeg.org/download.html"
            )
