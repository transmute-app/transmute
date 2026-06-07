import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from PIL import Image
from pillow_heif import HeifImagePlugin
import pillow_avif  # noqa: F401 — registers AVIF plugin on import
import pillow_jxl   # noqa: F401 — registers JPEG XL plugin on import

from core import get_settings
from .compressor_interface import CompressorInterface


# Encoder quality value (0-100, higher = better quality / larger file)
# keyed by compression-level preset. Used by the lossy encoders.
_QUALITY_BY_LEVEL: dict[str, int] = {
    'light': 90,
    'balanced': 75,
    'max': 50,
}
_DEFAULT_QUALITY = _QUALITY_BY_LEVEL['balanced']

# JPEG 2000 uses quality_layers (PSNR-like). Lower = smaller file.
_JP2_QUALITY_BY_LEVEL: dict[str, list[int]] = {
    'light': [90],
    'balanced': [70],
    'max': [40],
}
_DEFAULT_JP2_QUALITY = _JP2_QUALITY_BY_LEVEL['balanced']

# PNG zlib compression level (0-9, higher = smaller / slower). Always lossless.
_PNG_COMPRESS_LEVEL_BY_LEVEL: dict[str, int] = {
    'light': 6,
    'balanced': 9,
    'max': 9,
}
_DEFAULT_PNG_COMPRESS_LEVEL = _PNG_COMPRESS_LEVEL_BY_LEVEL['balanced']

# TIFF compressors. All lossless; tiff_deflate is typically the smallest.
_TIFF_COMPRESSION_BY_LEVEL: dict[str, str] = {
    'light': 'tiff_lzw',
    'balanced': 'tiff_deflate',
    'max': 'tiff_deflate',
}
_DEFAULT_TIFF_COMPRESSION = _TIFF_COMPRESSION_BY_LEVEL['balanced']

_LOSSY_QUALITY_FORMATS = {'jpeg', 'webp', 'avif', 'jxl', 'heif', 'heic'}
_NO_ALPHA_FORMATS = {'jpeg', 'jp2'}


class PillowCompressor(CompressorInterface):
    supported_formats: set = {
        'jpeg',
        'png',
        'webp',
        'avif',
        'jxl',
        'jp2',
        'heif',
        'heic',
        'tiff',
        'gif',
    }
    formats_with_compression_levels: set = {
        'jpeg',
        'png',
        'webp',
        'avif',
        'jxl',
        'jp2',
        'heif',
        'heic',
        'tiff',
    }

    def __init__(self, input_file: str, output_dir: str, media_type: str):
        """
        Initialize Pillow compressor.

        Args:
            input_file: Path to the input image file.
            output_dir: Directory where the compressed image will be saved.
            media_type: Image format (e.g., 'jpeg', 'png', 'webp').
        """
        super().__init__(input_file, output_dir, media_type)
        HeifImagePlugin.register_heif_opener()

    def can_compress(self) -> bool:
        """
        Check whether this compressor can compress the configured format.
        """
        return self.media_type in self.supported_formats

    def compress(self, overwrite: bool = True, compression_level: Optional[str] = None) -> list[str]:
        """
        Compress the input image, writing a same-format file to ``output_dir``.

        Args:
            overwrite: Whether to overwrite an existing output file (default: True).
            compression_level: One of ``"light"``, ``"balanced"``, ``"max"``.

        Returns:
            List containing the path to the compressed output file.

        Raises:
            FileNotFoundError: If the input file doesn't exist.
            ValueError: If the configured format isn't supported.
            RuntimeError: If image compression fails.
        """
        if not self.can_compress():
            raise ValueError(
                f"PillowCompressor does not support format: {self.media_type}"
            )

        if not os.path.isfile(self.input_file):
            raise FileNotFoundError(f"Input file not found: {self.input_file}")

        stem = Path(self.input_file).stem
        output_file = os.path.join(self.output_dir, f"{stem}.{self.media_type}")

        if not overwrite and os.path.exists(output_file):
            return [output_file]

        # Encode into the shared tmp dir so we can fall back to the original
        # bytes if the encoder would produce a larger file (and so input==output
        # callers don't lose their source mid-encode).
        original_size = os.path.getsize(self.input_file)
        tmp_dir = get_settings().tmp_dir
        tmp_fd, tmp_output = tempfile.mkstemp(
            prefix=f"compress-{stem}-",
            suffix=f".{self.media_type}",
            dir=str(tmp_dir),
        )
        os.close(tmp_fd)

        try:
            img = Image.open(self.input_file)
            img = self._normalize_mode(img, self.media_type)
            save_kwargs = self._build_save_kwargs(self.media_type, compression_level)
            img.save(tmp_output, **save_kwargs)
        except Exception as exc:
            if os.path.exists(tmp_output):
                os.remove(tmp_output)
            raise RuntimeError(f"Image compression failed: {exc}")

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

    @staticmethod
    def _normalize_mode(img: Image.Image, fmt: str) -> Image.Image:
        """Coerce image mode to something the target encoder accepts."""
        if fmt in _NO_ALPHA_FORMATS and img.mode in ('RGBA', 'LA', 'P'):
            if img.mode == 'P':
                img = img.convert('RGBA')
            if img.mode in ('RGBA', 'LA'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'LA':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1])
                img = background
        return img

    @staticmethod
    def _build_save_kwargs(fmt: str, level: Optional[str]) -> dict:
        kwargs: dict = {}

        if fmt in _LOSSY_QUALITY_FORMATS:
            kwargs['quality'] = _QUALITY_BY_LEVEL.get(level, _DEFAULT_QUALITY)
            if fmt == 'jpeg':
                kwargs['optimize'] = True
                kwargs['progressive'] = True
        elif fmt == 'jp2':
            kwargs['quality_layers'] = _JP2_QUALITY_BY_LEVEL.get(level, _DEFAULT_JP2_QUALITY)
        elif fmt == 'png':
            kwargs['optimize'] = True
            kwargs['compress_level'] = _PNG_COMPRESS_LEVEL_BY_LEVEL.get(
                level, _DEFAULT_PNG_COMPRESS_LEVEL
            )
        elif fmt == 'tiff':
            kwargs['compression'] = _TIFF_COMPRESSION_BY_LEVEL.get(
                level, _DEFAULT_TIFF_COMPRESSION
            )
        elif fmt == 'gif':
            # GIF uses palette + LZW; ``optimize`` strips redundant palette entries.
            kwargs['optimize'] = True

        return kwargs
