import os
import tempfile
import zipfile

from io import BytesIO
from pathlib import Path
from typing import Optional

import py7zr
import rarfile
from PIL import Image

from cbz.comic import ComicInfo
from cbz.constants import PageType
from cbz.page import PageInfo

from core.settings import get_settings
from .converter_interface import ConverterInterface


# Image extensions the cbz library supports as comic pages.
_IMAGE_EXTENSIONS = frozenset({
    '.jpg', '.jpeg', '.png', '.gif', '.bmp',
    '.tiff', '.tif', '.webp', '.jxl', '.avif',
})


class CBZConverter(ConverterInterface):
    """
    Converter for comic book archive formats to CBZ using the cbz library.

    Supports converting CBR (RAR-based), CB7 (7z-based), and PDF files
    into CBZ (ZIP-based) comic book archives.
    """

    supported_input_formats: set = {
        'cbz',
        'cbr',
        'cb7',
        'pdf',
        'pdf/a',
        'pdf/x',
        'pdf/e',
        'pdf/ua',
        'pdf/vt',
    }
    supported_output_formats: set = {
        'cbz',
        'pdf',
    }

    def __init__(self, input_file: str, output_dir: str, input_type: str, output_type: str):
        super().__init__(input_file, output_dir, input_type, output_type)

    def can_convert(self) -> bool:
        input_fmt = self.input_type.lower()
        output_fmt = self.output_type.lower()

        if input_fmt not in self.supported_input_formats:
            return False
        if output_fmt not in self.supported_output_formats:
            return False
        # PDF→PDF and CBZ→CBZ are identity conversions.
        if input_fmt.startswith('pdf') and output_fmt == 'pdf':
            return False
        if input_fmt == 'cbz' and output_fmt == 'cbz':
            return False

        return True

    @classmethod
    def get_formats_compatible_with(cls, format_type: str) -> set:
        fmt = format_type.lower()
        if fmt not in cls.supported_input_formats:
            return set()
        compatible = cls.supported_output_formats.copy()
        # Exclude identity conversions.
        if fmt.startswith('pdf'):
            compatible.discard('pdf')
        if fmt == 'cbz':
            compatible.discard('cbz')
        return compatible

    def _convert_cbr_to_cbz(self, output_file: str) -> str:
        with tempfile.TemporaryDirectory(dir=get_settings().tmp_dir) as tmp:
            with rarfile.RarFile(self.input_file, 'r') as rf:
                self._safe_extract_rar(rf, tmp)

            images = self._collect_images(tmp)
            if not images:
                raise RuntimeError("CBR archive contains no supported image files.")

            last_idx = len(images) - 1
            pages: list[PageInfo] = []
            for i, img_path in enumerate(images):
                if i == 0:
                    page_type = PageType.FRONT_COVER
                elif i == last_idx:
                    page_type = PageType.BACK_COVER
                else:
                    page_type = PageType.STORY
                pages.append(PageInfo.load(path=str(img_path), type=page_type))

            comic = ComicInfo.from_pages(pages=pages)
            Path(output_file).write_bytes(comic.pack(compression=zipfile.ZIP_DEFLATED))

        return output_file

    def _convert_pdf_to_cbz(self, output_file: str) -> str:
        try:
            comic = ComicInfo.from_pdf(self.input_file)
        except (AssertionError, Exception) as exc:
            raise RuntimeError(
                f"PDF contains no extractable images: {exc}"
            ) from exc
        Path(output_file).write_bytes(comic.pack(compression=zipfile.ZIP_DEFLATED))
        return output_file

    @staticmethod
    def _safe_extract_7z(sz: py7zr.SevenZipFile, dest: str) -> None:
        """Extract a 7z archive, rejecting members with path traversal."""
        real_dest = os.path.realpath(dest)
        for entry in sz.list():
            resolved = os.path.realpath(os.path.join(dest, entry.filename))
            if not resolved.startswith(real_dest + os.sep) and resolved != real_dest:
                raise ValueError(f"Path traversal detected in 7z member: {entry.filename}")
        sz.extractall(path=dest)  # nosec B202

    @staticmethod
    def _safe_extract_rar(rf: rarfile.RarFile, dest: str) -> None:
        """Extract a RAR archive, rejecting members with path traversal."""
        real_dest = os.path.realpath(dest)
        for entry in rf.infolist():
            resolved = os.path.realpath(os.path.join(dest, entry.filename))
            if not resolved.startswith(real_dest + os.sep) and resolved != real_dest:
                raise ValueError(f"Path traversal detected in RAR member: {entry.filename}")
        rf.extractall(path=dest)

    @staticmethod
    def _collect_images(directory: str) -> list[Path]:
        """Walk *directory* and return image paths sorted by name."""
        images: list[Path] = []
        for root, _dirs, files in os.walk(directory):
            for fname in sorted(files):
                if Path(fname).suffix.lower() in _IMAGE_EXTENSIONS:
                    images.append(Path(root) / fname)
        images.sort(key=lambda p: p.name)
        return images

    def _convert_cb7_to_cbz(self, output_file: str) -> str:
        with tempfile.TemporaryDirectory(dir=get_settings().tmp_dir) as tmp:
            with py7zr.SevenZipFile(self.input_file, 'r') as sz:
                self._safe_extract_7z(sz, tmp)

            images = self._collect_images(tmp)
            if not images:
                raise RuntimeError("CB7 archive contains no supported image files.")

            last_idx = len(images) - 1
            pages: list[PageInfo] = []
            for i, img_path in enumerate(images):
                if i == 0:
                    page_type = PageType.FRONT_COVER
                elif i == last_idx:
                    page_type = PageType.BACK_COVER
                else:
                    page_type = PageType.STORY
                pages.append(PageInfo.load(path=str(img_path), type=page_type))

            comic = ComicInfo.from_pages(pages=pages)
            Path(output_file).write_bytes(comic.pack(compression=zipfile.ZIP_DEFLATED))

        return output_file

    def _load_images_from_cbz(self) -> list[Image.Image]:
        """Extract images from a CBZ (ZIP) archive."""
        images: list[Image.Image] = []
        with zipfile.ZipFile(self.input_file, 'r') as zf:
            names = sorted(
                n for n in zf.namelist()
                if Path(n).suffix.lower() in _IMAGE_EXTENSIONS
                and not Path(n).name.startswith('.')
            )
            for name in names:
                img = Image.open(BytesIO(zf.read(name)))
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                images.append(img)
        return images

    def _load_images_from_cbr(self) -> list[Image.Image]:
        """Extract images from a CBR (RAR) archive."""
        images: list[Image.Image] = []
        with rarfile.RarFile(self.input_file, 'r') as rf:
            names = sorted(
                n for n in rf.namelist()
                if Path(n).suffix.lower() in _IMAGE_EXTENSIONS
                and not Path(n).name.startswith('.')
            )
            for name in names:
                img = Image.open(BytesIO(rf.read(name)))
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                images.append(img)
        return images

    def _load_images_from_cb7(self) -> list[Image.Image]:
        """Extract images from a CB7 (7z) archive."""
        images: list[Image.Image] = []
        with tempfile.TemporaryDirectory(dir=get_settings().tmp_dir) as tmp:
            with py7zr.SevenZipFile(self.input_file, 'r') as sz:
                self._safe_extract_7z(sz, tmp)
            for img_path in self._collect_images(tmp):
                img = Image.open(str(img_path))
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                images.append(img)
        return images

    def _convert_to_pdf(self, output_file: str) -> str:
        """Convert any supported comic archive to a multi-page PDF."""
        input_fmt = self.input_type.lower()

        if input_fmt == 'cbz':
            images = self._load_images_from_cbz()
        elif input_fmt == 'cbr':
            images = self._load_images_from_cbr()
        elif input_fmt == 'cb7':
            images = self._load_images_from_cb7()
        else:
            raise ValueError(
                f"Conversion from {self.input_type} to PDF is not supported."
            )

        if not images:
            raise RuntimeError("Archive contains no supported image files.")

        images[0].save(
            output_file, 'PDF', save_all=True, append_images=images[1:],
        )
        return output_file

    def convert(self, overwrite: bool = True, quality: Optional[str] = None) -> list[str]:
        if not self.can_convert():
            raise ValueError(
                f"Conversion from {self.input_type} to {self.output_type} is not supported."
            )

        if not os.path.isfile(self.input_file):
            raise FileNotFoundError(f"Input file not found: {self.input_file}")

        input_filename = Path(self.input_file).stem
        output_file = os.path.join(self.output_dir, f"{input_filename}.{self.output_type}")

        if not overwrite and os.path.exists(output_file):
            return [output_file]

        input_fmt = self.input_type.lower()
        output_fmt = self.output_type.lower()

        # --- PDF output ---
        if output_fmt == 'pdf':
            return [self._convert_to_pdf(output_file)]

        # --- CBZ output ---
        if input_fmt == 'cbr':
            return [self._convert_cbr_to_cbz(output_file)]
        elif input_fmt == 'cb7':
            return [self._convert_cb7_to_cbz(output_file)]
        elif input_fmt.startswith('pdf'):
            return [self._convert_pdf_to_cbz(output_file)]

        raise ValueError(
            f"Conversion from {self.input_type} to {self.output_type} is not supported."
        )
