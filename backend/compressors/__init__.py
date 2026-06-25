from .compressor_interface import CompressorInterface
from .ffmpeg_compress import FFmpegCompressor
from .pillow_compress import PillowCompressor
from .pymupdf_compress import PyMuPDFCompressor

__all__ = [
    "CompressorInterface",
    "FFmpegCompressor",
    "PillowCompressor",
    "PyMuPDFCompressor",
]
