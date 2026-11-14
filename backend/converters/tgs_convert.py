import gzip
import json
import os
import shutil
import subprocess  # nosec B404
import sys
import tempfile
from pathlib import Path
from typing import Optional

from .converter_interface import ConverterInterface
from .ffmpeg_convert import FFmpegConverter

from rlottie_python import LottieAnimation

_ANIMATED_FORMATS: set = {'gif', 'webp', 'apng', 'mp4'}


def _ffmpeg_available() -> bool:
    """Return True if the FFmpeg binary used by FFmpegConverter is callable."""
    try:
        subprocess.run(  # nosec B603
            [FFmpegConverter.ffmpeg_path, '-version'],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


class TGSConverter(ConverterInterface):
    """
    Converter for Telegram animated stickers (.tgs).

    A .tgs file is a gzip-compressed Lottie JSON document. This converter
    always supports decompressing to plain Lottie JSON. Animated outputs
    (gif, webp, apng, mp4) are exposed only when the rlottie-python
    renderer is available; mp4 additionally requires FFmpeg.
    """

    supported_input_formats: set = {'tgs'}
    # Base output set — the dynamic compatibility logic below adds animated
    # targets when the optional renderer is available.
    supported_output_formats: set = {'json', 'gif', 'webp', 'apng', 'mp4'}

    def __init__(self, input_file: str, output_dir: str, input_type: str, output_type: str):
        super().__init__(input_file, output_dir, input_type, output_type)

    @classmethod
    def _animated_outputs_available(cls) -> set:
        """Return the set of animated outputs that this environment can produce."""
        outputs = {'gif', 'webp', 'apng'}
        if _ffmpeg_available():
            outputs.add('mp4')
        return outputs

    def can_convert(self) -> bool:
        if self.input_type.lower() != 'tgs':
            return False
        output_fmt = self.output_type.lower()
        if output_fmt == 'json':
            return True
        if output_fmt in _ANIMATED_FORMATS:
            return output_fmt in self._animated_outputs_available()
        return False

    @classmethod
    def get_formats_compatible_with(cls, format_type: str) -> set:
        """
        Get the set of compatible output formats for a given input format.

        ``.tgs -> json`` is always advertised. Animated outputs are advertised
        only when ``rlottie-python`` is importable; ``mp4`` additionally
        requires FFmpeg.
        """
        fmt = format_type.lower()
        if fmt != 'tgs':
            return set()
        return {'json'} | cls._animated_outputs_available()

    @staticmethod
    def _decompress_tgs(input_file: str) -> bytes:
        """Read and gunzip a .tgs file, returning the raw Lottie JSON bytes."""
        with gzip.open(input_file, 'rb') as f:
            return f.read()

    def _convert_to_json(self, output_file: str) -> str:
        """Decompress the .tgs into plain Lottie JSON on disk."""
        raw = self._decompress_tgs(self.input_file)
        # Validate the payload is JSON before writing so callers see a clean
        # error rather than a silently-corrupt output file.
        try:
            json.loads(raw)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"TGS payload is not valid Lottie JSON: {e}")
        with open(output_file, 'wb') as f:
            f.write(raw)
        return output_file

    def _convert_to_animation(self, output_file: str, output_fmt: str) -> str:
        """Render the .tgs into an animated raster file via rlottie."""

        if output_fmt == 'mp4':
            if not _ffmpeg_available():
                raise RuntimeError(
                    "FFmpeg is required for TGS to MP4 conversion but could "
                    "not be found."
                )
            # rlottie cannot write mp4 directly; render to apng first then
            # transcode with ffmpeg, which is already a runtime dependency.
            with tempfile.TemporaryDirectory() as tmpdir:
                apng_path = os.path.join(tmpdir, 'frames.apng')
                with LottieAnimation.from_tgs(self.input_file) as anim:
                    anim.save_animation(apng_path)
                cmd = [
                    FFmpegConverter.ffmpeg_path,
                    '-y',
                    '-i', apng_path,
                    '-pix_fmt', 'yuv420p',
                    # Ensure even dimensions for yuv420p.
                    '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2',
                    '-movflags', '+faststart',
                    *FFmpegConverter.video_track_timescale_args,
                    output_file,
                ]
                try:
                    subprocess.run(  # nosec B603
                        cmd,
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                except subprocess.CalledProcessError as e:
                    stderr = e.stderr.decode('utf-8', errors='replace') if e.stderr else ''
                    raise RuntimeError(f"FFmpeg failed to encode mp4: {stderr}")
            return output_file

        # gif / webp / apng — rlottie picks encoder from file extension.
        with LottieAnimation.from_tgs(self.input_file) as anim:
            anim.save_animation(output_file)
        return output_file

    def convert(self, overwrite: bool = True, quality: Optional[str] = None) -> list[str]:
        if not self.can_convert():
            raise ValueError(
                f"Cannot convert {self.input_type} to {self.output_type}."
            )

        if not os.path.isfile(self.input_file):
            raise FileNotFoundError(f"Input file not found: {self.input_file}")

        input_filename = Path(self.input_file).stem
        output_fmt = self.output_type.lower()
        output_file = os.path.join(self.output_dir, f"{input_filename}.{output_fmt}")

        if not overwrite and os.path.exists(output_file):
            return [output_file]

        try:
            if output_fmt == 'json':
                self._convert_to_json(output_file)
            else:
                self._convert_to_animation(output_file, output_fmt)
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"TGS conversion failed: {e}")

        return [output_file]
