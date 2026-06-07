import os
from typing import Optional

from core import media_type_aliases


def _normalize_compressor_media_type(media_type: str) -> str:
    """Normalize media types for compressor execution."""
    normalized = media_type.lower()
    return media_type_aliases.get(normalized, normalized)


class CompressorInterface:
    """Base contract for same-format file compressors.

    Compressors reduce the size of a file without changing its format.
    Format-changing operations belong in ``ConverterInterface`` subclasses.
    """

    supported_formats: set = set()  # Formats this compressor can compress (input == output)
    compression_levels: set = set()  # Optional compression-level presets (e.g. "light", "balanced", "max")
    formats_with_compression_levels: set = set()  # Subset of supported_formats that honor a compression_level argument

    compression_levels = {
        'light',
        'balanced',
        'max',
    }

    def __init__(self, input_file: str, output_dir: str, media_type: str):
        """
        Initialize compressor interface.

        Args:
            input_file: Path to the input file.
            output_dir: Directory where the compressed output file will be saved.
            media_type: Format of the input/output file (e.g., "pdf", "mp4", "png").
        """
        self.input_file = input_file
        self.output_dir = output_dir
        self.requested_media_type = media_type.lower()
        self.media_type = _normalize_compressor_media_type(self.requested_media_type)

        os.makedirs(self.output_dir, exist_ok=True)

    def can_compress(self) -> bool:
        """
        Check if this compressor can compress the configured ``media_type``.

        Returns:
            True if compression is possible, False otherwise.
        """
        raise NotImplementedError("can_compress method must be implemented by subclasses.")

    @classmethod
    def can_register(cls) -> bool:
        """
        Check if this compressor can be registered based on required non-pip dependencies.

        Override only when registration depends on a runtime condition such
        as the presence of an external binary. Optional pip dependencies
        should be lazy-imported inside ``compress()`` so the package stays
        importable when they are absent.
        """
        return True

    @classmethod
    def supports_format(cls, media_type: str) -> bool:
        """
        Whether this compressor can compress the given media type.

        Args:
            media_type: Format to check (alias-tolerant, case-insensitive).
        """
        normalized = _normalize_compressor_media_type(media_type)
        return normalized in cls.supported_formats

    @classmethod
    def get_compression_levels(cls) -> set:
        """
        Get the set of compression-level presets available for this compressor.

        ``light`` favors fidelity over size reduction; ``max`` favors maximum
        size reduction; ``balanced`` is the default middle ground.
        """
        return cls.compression_levels

    @classmethod
    def get_formats_with_compression_levels(cls) -> set:
        """
        Get the set of formats that honor a compression-level argument for this compressor.
        """
        return cls.formats_with_compression_levels

    def compress(self, overwrite: bool = True, compression_level: Optional[str] = None) -> list[str]:
        """
        Compress the input file, writing the result into ``output_dir``.

        Args:
            overwrite: Whether to overwrite an existing output file (default: True).
            compression_level: Optional preset selecting how aggressively to compress
                (e.g., "light", "balanced", "max").

        Returns:
            List of paths to the produced output files.
        """
        raise NotImplementedError("compress method must be implemented by subclasses.")
