import subprocess  # nosec B404
import sys
import os
import math
import json
import shutil
import tempfile
import logging
from pathlib import Path
from typing import Optional

from core import get_settings, validate_safe_path
from .compressor_interface import CompressorInterface


logger = logging.getLogger(__name__)


# --- Compression-level → encoder setting maps -------------------------------
#
# Compression keeps the source format but re-encodes the media at lower
# quality so the output is smaller. ``light`` favors fidelity over size
# reduction, ``max`` favors maximum size reduction, ``balanced`` sits between.

# H.264 CRF (Constant Rate Factor, 0-51, higher = smaller / lower quality).
_H264_CRF_BY_LEVEL: dict[str, int] = {
    'light': 26,
    'balanced': 30,
    'max': 33,
}
_DEFAULT_H264_CRF = _H264_CRF_BY_LEVEL['balanced']

# libx264 encoding preset. Slower presets compress better at the cost of time.
_H264_PRESET_BY_LEVEL: dict[str, str] = {
    'light': 'fast',
    'balanced': 'medium',
    'max': 'slow',
}
_DEFAULT_H264_PRESET = _H264_PRESET_BY_LEVEL['balanced']

# VP9 CRF (0-63, higher = smaller / lower quality). Paired with ``-b:v 0`` for
# constant-quality mode.
_VP9_CRF_BY_LEVEL: dict[str, int] = {
    'light': 31,
    'balanced': 36,
    'max': 41,
}
_DEFAULT_VP9_CRF = _VP9_CRF_BY_LEVEL['balanced']

# MPEG-family qscale (``-q:v``, ~1-31, higher = smaller / lower quality). Used
# by the default codecs of flv/mpeg/wmv/asf containers.
_QSCALE_BY_LEVEL: dict[str, int] = {
    'light': 5,
    'balanced': 9,
    'max': 15,
}
_DEFAULT_QSCALE = _QSCALE_BY_LEVEL['balanced']

# Audio bitrate per level for lossy audio codecs (and the audio track of
# re-encoded video). Lower bitrate = smaller / lower quality.
_AUDIO_BITRATE_BY_LEVEL: dict[str, str] = {
    'light': '160k',
    'balanced': '112k',
    'max': '80k',
}
_DEFAULT_AUDIO_BITRATE = _AUDIO_BITRATE_BY_LEVEL['balanced']

# AC-3 has a higher practical minimum bitrate than other codecs.
_AC3_BITRATE_BY_LEVEL: dict[str, str] = {
    'light': '256k',
    'balanced': '192k',
    'max': '128k',
}
_DEFAULT_AC3_BITRATE = _AC3_BITRATE_BY_LEVEL['balanced']

# FLAC is lossless: a higher compression level (0-12) produces a smaller file
# with no quality loss, at the cost of more encoding time.
_FLAC_COMPRESSION_BY_LEVEL: dict[str, int] = {
    'light': 8,
    'balanced': 10,
    'max': 12,
}
_DEFAULT_FLAC_COMPRESSION = _FLAC_COMPRESSION_BY_LEVEL['balanced']


class FFmpegCompressor(CompressorInterface):
    """Same-format audio/video compressor backed by FFmpeg.

    Size reduction comes from re-encoding the media at a lower quality while
    keeping the original container/format. Video containers are re-encoded with
    an efficient codec (H.264 for most, VP9 for WebM) using a Constant Rate
    Factor; older MPEG-family containers use qscale; audio is re-encoded at a
    lower bitrate.

    If the produced file is not smaller than the original, the original bytes
    are kept instead.
    """

    # Video containers re-encoded to H.264 + AAC. H.264 is broadly supported by
    # all of these containers and guarantees CRF-based size control regardless
    # of the source codec.
    _h264_video_formats: set = {
        'mp4',
        'mov',
        'mkv',
        'm4v',
        'avi',
        'ts',
        '3gp',
        'f4v',
    }
    # WebM must use a WebM-compatible codec (VP9 + Opus).
    _vp9_video_formats: set = {'webm'}
    # MPEG-family containers whose default codecs honor qscale (``-q:v``).
    _qscale_video_formats: set = {
        'flv',
        'mpeg',
        'wmv',
        'asf',
    }
    # Lossy audio formats re-encoded at a lower bitrate using each container's
    # default codec, plus FLAC which is shrunk losslessly via its compression
    # level rather than by lowering bitrate.
    audio_formats: set = {
        'mp3',
        'aac',
        'wma',
        'm4a',
        'opus',
        'mp2',
        'ac3',
        'oga',
        'flac',
    }

    video_formats: set = _h264_video_formats | _vp9_video_formats | _qscale_video_formats

    supported_formats: set = video_formats | audio_formats
    formats_with_compression_levels: set = supported_formats

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

    def can_compress(self) -> bool:
        """
        Check whether this compressor can compress the configured format.
        """
        return self.media_type in self.supported_formats

    def get_size_based_timeout_seconds(self) -> int:
        """Estimate a compression timeout from input file size."""
        input_size_bytes = Path(self.input_file).stat().st_size
        input_size_mb = max(1, math.ceil(input_size_bytes / (1024 * 1024)))
        timeout_seconds = self.min_timeout_seconds + (input_size_mb * self.timeout_seconds_per_mb)
        return min(timeout_seconds, self.max_timeout_seconds)

    def get_media_probe_data(self) -> dict | None:
        """Return ffprobe metadata for timeout estimation.

        Timeout estimation should not fail compression just because ffprobe is
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

    def get_media_based_timeout_seconds(self) -> int | None:
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
        else:
            # Re-encoding video is the most expensive case; scale by resolution.
            seconds_per_second = 1.0 * self.get_video_resolution_factor(probe_data)

        timeout_seconds = self.min_timeout_seconds + math.ceil(duration_seconds * seconds_per_second)
        return min(timeout_seconds, self.max_timeout_seconds)

    def get_compression_timeout_seconds(self) -> int:
        """Estimate a compression timeout from media metadata with size fallback."""
        size_based_timeout = self.get_size_based_timeout_seconds()
        media_based_timeout = self.get_media_based_timeout_seconds()
        if media_based_timeout is None:
            return size_based_timeout
        return max(size_based_timeout, media_based_timeout)

    def _build_codec_args(self, compression_level: Optional[str]) -> list[str]:
        """Build the FFmpeg codec/quality arguments for the configured format."""
        fmt = self.media_type
        args: list[str] = []

        if fmt in self.audio_formats:
            # Audio-only output: drop any video stream.
            args.append('-vn')
            if fmt == 'flac':
                # FLAC is lossless; shrink it by raising the (lossless)
                # compression level instead of lowering bitrate.
                level = _FLAC_COMPRESSION_BY_LEVEL.get(
                    compression_level, _DEFAULT_FLAC_COMPRESSION
                )
                args.extend(['-c:a', 'flac', '-compression_level', str(level)])
                return args
            # Re-encode the audio at a lower bitrate using the container's
            # default codec.
            if fmt == 'ac3':
                bitrate = _AC3_BITRATE_BY_LEVEL.get(compression_level, _DEFAULT_AC3_BITRATE)
            else:
                bitrate = _AUDIO_BITRATE_BY_LEVEL.get(compression_level, _DEFAULT_AUDIO_BITRATE)
            args.extend(['-b:a', bitrate])
            return args

        if fmt in self._h264_video_formats:
            crf = _H264_CRF_BY_LEVEL.get(compression_level, _DEFAULT_H264_CRF)
            preset = _H264_PRESET_BY_LEVEL.get(compression_level, _DEFAULT_H264_PRESET)
            audio_bitrate = _AUDIO_BITRATE_BY_LEVEL.get(compression_level, _DEFAULT_AUDIO_BITRATE)
            args.extend([
                '-c:v', 'libx264',
                '-crf', str(crf),
                '-preset', preset,
                # yuv420p keeps the output broadly playable and strips alpha.
                '-pix_fmt', 'yuv420p',
                '-c:a', 'aac',
                '-b:a', audio_bitrate,
            ])
            return args

        if fmt in self._vp9_video_formats:
            crf = _VP9_CRF_BY_LEVEL.get(compression_level, _DEFAULT_VP9_CRF)
            audio_bitrate = _AUDIO_BITRATE_BY_LEVEL.get(compression_level, _DEFAULT_AUDIO_BITRATE)
            args.extend([
                '-c:v', 'libvpx-vp9',
                '-crf', str(crf),
                # ``-b:v 0`` selects constant-quality (CRF) mode for libvpx-vp9.
                '-b:v', '0',
                '-c:a', 'libopus',
                '-b:a', audio_bitrate,
            ])
            return args

        # MPEG-family containers: re-encode with the container default codecs
        # and control size via qscale.
        qscale = _QSCALE_BY_LEVEL.get(compression_level, _DEFAULT_QSCALE)
        audio_bitrate = _AUDIO_BITRATE_BY_LEVEL.get(compression_level, _DEFAULT_AUDIO_BITRATE)
        args.extend([
            '-q:v', str(qscale),
            '-b:a', audio_bitrate,
        ])
        return args

    def compress(self, overwrite: bool = True, compression_level: Optional[str] = None) -> list[str]:
        """
        Compress the input audio/video file, writing a same-format file to
        ``output_dir``.

        Args:
            overwrite: Whether to overwrite an existing output file (default: True).
            compression_level: One of ``"light"``, ``"balanced"``, ``"max"``.

        Returns:
            List containing the path to the compressed output file.

        Raises:
            FileNotFoundError: If the input file doesn't exist.
            ValueError: If the configured format isn't supported.
            RuntimeError: If FFmpeg compression fails.
        """
        if not self.can_compress():
            raise ValueError(
                f"FFmpegCompressor does not support format: {self.media_type}"
            )

        if not os.path.isfile(self.input_file):
            raise FileNotFoundError(f"Input file not found: {self.input_file}")

        stem = Path(self.input_file).stem
        output_file = os.path.join(self.output_dir, f"{stem}.{self.media_type}")

        if not overwrite and os.path.exists(output_file):
            return [output_file]

        # Encode into the shared tmp dir so we can fall back to the original
        # bytes if the re-encode would produce a larger file (and so input==output
        # callers don't lose their source mid-encode).
        original_size = os.path.getsize(self.input_file)
        tmp_dir = get_settings().tmp_dir
        tmp_fd, tmp_output = tempfile.mkstemp(
            prefix=f"compress-{stem}-",
            suffix=f".{self.media_type}",
            dir=str(tmp_dir),
        )
        os.close(tmp_fd)

        validate_safe_path(self.input_file)
        cmd = [
            self.ffmpeg_path,
            '-y',  # Always overwrite the pre-created tmp file.
            '-i', self.input_file,
        ]
        cmd.extend(self._build_codec_args(compression_level))
        cmd.append(tmp_output)

        timeout_seconds = self.get_compression_timeout_seconds()

        try:
            # Subprocess is safe here because the input file path is validated
            # and the command is constructed without user input.
            subprocess.run(  # nosec B603
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
                timeout=timeout_seconds,
            )
        except subprocess.CalledProcessError as exc:
            if os.path.exists(tmp_output):
                os.remove(tmp_output)
            raise RuntimeError(f"FFmpeg compression failed: {exc.stderr}")
        except subprocess.TimeoutExpired:
            if os.path.exists(tmp_output):
                os.remove(tmp_output)
            raise RuntimeError(
                f"FFmpeg compression timed out after {timeout_seconds} seconds. "
                "Try a smaller file or a lighter compression level."
            )
        except FileNotFoundError:
            if os.path.exists(tmp_output):
                os.remove(tmp_output)
            raise RuntimeError(
                "FFmpeg not found. Please install FFmpeg: "
                "https://ffmpeg.org/download.html"
            )

        try:
            if os.path.getsize(tmp_output) < original_size:
                shutil.move(tmp_output, output_file)
            else:
                if os.path.abspath(self.input_file) != os.path.abspath(output_file):
                    shutil.copy2(self.input_file, output_file)
        finally:
            if os.path.exists(tmp_output):
                os.remove(tmp_output)

        return [output_file]
