import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from core import get_settings
from .compressor_interface import CompressorInterface


# JPEG encoder quality (0-100, higher = better quality / larger file) used when
# re-encoding raster images embedded in the PDF, keyed by compression-level
# preset. Lower quality favors smaller output at the cost of image fidelity.
_IMAGE_QUALITY_BY_LEVEL: dict[str, int] = {
    'light': 80,
    'balanced': 60,
    'max': 40,
}
_DEFAULT_IMAGE_QUALITY = _IMAGE_QUALITY_BY_LEVEL['balanced']

# Whether to halve the resolution of large embedded images for a given preset.
# Downscaling degrades image detail but can dramatically shrink image-heavy
# (e.g. scanned) PDFs. Text and vector content are never affected.
_DOWNSCALE_LARGE_IMAGES_BY_LEVEL: dict[str, bool] = {
    'light': False,
    'balanced': False,
    'max': True,
}

# Only consider an embedded image "large" (and therefore eligible for the
# optional downscale pass) when either dimension exceeds this pixel threshold.
_DOWNSCALE_MIN_DIMENSION = 1000


class PyMuPDFCompressor(CompressorInterface):
    """Same-format PDF compressor backed by PyMuPDF (fitz).

    Size reduction comes from two passes:

    1. Lossy re-encoding of embedded raster images to lower-quality JPEG
       (optionally downscaling large images for the ``max`` preset). Document
       text and vector graphics are left untouched, so the overall content is
       preserved while image fidelity is degraded.
    2. A lossless cleanup pass on save (object garbage collection plus stream
       deflation) that removes unused objects and recompresses streams.

    If the produced file is not smaller than the original, the original bytes
    are kept instead.
    """

    supported_formats: set = {'pdf'}
    formats_with_compression_levels: set = {'pdf'}

    def can_compress(self) -> bool:
        """
        Check whether this compressor can compress the configured format.
        """
        return self.media_type in self.supported_formats

    def compress(self, overwrite: bool = True, compression_level: Optional[str] = None) -> list[str]:
        """
        Compress the input PDF, writing a same-format file to ``output_dir``.

        Args:
            overwrite: Whether to overwrite an existing output file (default: True).
            compression_level: One of ``"light"``, ``"balanced"``, ``"max"``.

        Returns:
            List containing the path to the compressed output file.

        Raises:
            FileNotFoundError: If the input file doesn't exist.
            ValueError: If the configured format isn't supported.
            RuntimeError: If PDF compression fails.
        """
        import fitz  # PyMuPDF — lazy-imported so the package stays importable.

        if not self.can_compress():
            raise ValueError(
                f"PyMuPDFCompressor does not support format: {self.media_type}"
            )

        if not os.path.isfile(self.input_file):
            raise FileNotFoundError(f"Input file not found: {self.input_file}")

        stem = Path(self.input_file).stem
        output_file = os.path.join(self.output_dir, f"{stem}.{self.media_type}")

        if not overwrite and os.path.exists(output_file):
            return [output_file]

        quality = _IMAGE_QUALITY_BY_LEVEL.get(compression_level, _DEFAULT_IMAGE_QUALITY)
        downscale = _DOWNSCALE_LARGE_IMAGES_BY_LEVEL.get(compression_level, False)

        # Encode into the shared tmp dir so we can fall back to the original
        # bytes if the encode would produce a larger file (and so input==output
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
            doc = fitz.open(self.input_file)
            try:
                self._recompress_images(fitz, doc, quality, downscale)
                doc.save(
                    tmp_output,
                    garbage=4,
                    deflate=True,
                    deflate_images=True,
                    deflate_fonts=True,
                    clean=True,
                )
            finally:
                doc.close()
        except Exception as exc:
            if os.path.exists(tmp_output):
                os.remove(tmp_output)
            raise RuntimeError(f"PDF compression failed: {exc}")

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
    def _recompress_images(fitz, doc, quality: int, downscale: bool) -> None:
        """Re-encode embedded raster images to lower-quality JPEG in place.

        Images carrying transparency (an alpha channel or a soft mask) are left
        untouched, since flattening them to JPEG would discard the mask and can
        visibly corrupt the page. An image is only replaced when the new JPEG
        stream is actually smaller than the existing one.
        """
        # Collect each image xref once, remembering a page that displays it so
        # the replacement can be applied via that page.
        xref_to_page: dict[int, int] = {}
        for page_index in range(doc.page_count):
            for img in doc[page_index].get_images(full=True):
                xref = img[0]
                xref_to_page.setdefault(xref, page_index)

        for xref, page_index in xref_to_page.items():
            try:
                # An image referencing a soft mask carries transparency; skip
                # it to avoid flattening the mask away.
                smask = doc.xref_get_key(xref, "SMask")
                if smask and smask[0] != "null":
                    continue

                pix = fitz.Pixmap(doc, xref)

                # Stencil masks and alpha-bearing images can't round-trip
                # through JPEG without losing information; leave them as-is.
                if pix.alpha or pix.colorspace is None:
                    continue

                # JPEG can't encode CMYK via PyMuPDF; convert to RGB first.
                if pix.n - pix.alpha >= 4:
                    pix = fitz.Pixmap(fitz.csRGB, pix)

                if downscale and (pix.width > _DOWNSCALE_MIN_DIMENSION or
                                  pix.height > _DOWNSCALE_MIN_DIMENSION):
                    pix.shrink(1)  # Halve each dimension.

                new_stream = pix.tobytes("jpeg", jpg_quality=quality)

                try:
                    existing_size = len(doc.xref_stream_raw(xref))
                except Exception:
                    existing_size = None

                if existing_size is None or len(new_stream) < existing_size:
                    doc[page_index].replace_image(xref, stream=new_stream)
            except Exception:
                # Any single problematic image is skipped rather than failing
                # the whole compression job.
                continue
