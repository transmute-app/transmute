from .compressor_interface import CompressorInterface
from .pillow_compress import PillowCompressor
from .pymupdf_compress import PyMuPDFCompressor

__all__ = [
    "CompressorInterface",
    "PillowCompressor",
    "PyMuPDFCompressor",
]
