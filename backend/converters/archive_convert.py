import io
import os
import logging
import shutil
import tarfile
import tempfile
import rarfile
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

import py7zr
import pyzstd

from core.settings import get_settings
from .converter_interface import ConverterInterface


logger = logging.getLogger(__name__)

class ArchiveConverter(ConverterInterface):
    """
    Converter for repacking between archive formats like ZIP and TAR.GZ.
    """

    _7Z_WRITE_FILTERS = [{"id": py7zr.FILTER_LZMA2, "preset": 1}]

    supported_input_formats: set = {
        '7z',
        'zip',
        'tar',
        'rar',
        'tar.gz',
        'tar.bz2',
        'tar.xz',
        'tar.zst',
    }
    supported_output_formats: set = {
        '7z',
        'zip',
        'tar',
        'tar.gz',
        'tar.bz2',
        'tar.xz',
        'tar.zst',
    }

    def __init__(self, input_file: str, output_dir: str, input_type: str, output_type: str):
        """
        Initialize Archive converter.

        Args:
            input_file: Path to the input archive file
            output_dir: Directory where the converted file will be saved
            input_type: Input file format (e.g., 'zip', 'tar.gz')
            output_type: Output file format (e.g., 'zip', 'tar.gz')
        """
        super().__init__(input_file, output_dir, input_type, output_type)
    
    @classmethod
    def can_register(cls) -> bool:
        """
        Check if a RAR extraction tool (unar, unrar, 7z, or bsdtar) is available.

        Returns:
            True if at least one supported tool is found, False otherwise.
        """
        try:
            rarfile.tool_setup(force=True)
            return True
        except rarfile.RarCannotExec:
            return False

    def can_convert(self) -> bool:
        """
        Check if the input file can be converted to the output format.

        Returns:
            True if conversion is possible, False otherwise.
        """
        input_fmt = self.input_type.lower()
        output_fmt = self.output_type.lower()

        if input_fmt not in self.supported_input_formats:
            return False
        if output_fmt not in self.supported_output_formats:
            return False

        return True

    @classmethod
    def get_formats_compatible_with(cls, format_type: str) -> set:
        """
        Get the set of compatible output formats for a given input format.

        Args:
            format_type: The input format to check compatibility for.

        Returns:
            Set of compatible output formats.
        """
        fmt = format_type.lower()
        if fmt not in cls.supported_input_formats:
            return set()
        return cls.supported_output_formats - {fmt}

    @contextmanager
    def _open_tar_for_reading(self) -> Iterator[tarfile.TarFile]:
        """Open the input tar archive, streaming zstandard input when needed."""
        if self.input_type.lower() == 'tar.zst':
            with open(self.input_file, 'rb') as raw_in:
                with pyzstd.ZstdFile(raw_in, mode='rb') as zstd_in:
                    with tarfile.open(fileobj=zstd_in, mode='r|') as tar:
                        yield tar
            return

        with tarfile.open(self.input_file, 'r:*') as tar:
            yield tar

    @contextmanager
    def _open_tar_for_writing(self, output_file: str, compression: str = '') -> Iterator[tarfile.TarFile]:
        """Open a tar archive for writing, handling zstandard compression transparently."""
        if compression == 'zst':
            with open(output_file, 'wb') as raw_out:
                with pyzstd.ZstdFile(raw_out, mode='wb') as zstd_out:
                    with tarfile.open(fileobj=zstd_out, mode='w|') as tar:
                        yield tar
            return

        tar_mode = f"w:{compression}" if compression else 'w'
        with tarfile.open(output_file, tar_mode) as tar:
            yield tar

    def _iter_tar_members(self, tar: tarfile.TarFile) -> Iterator[tarfile.TarInfo]:
        """Yield TAR members sequentially so streamed archives remain readable."""
        while True:
            member = tar.next()
            if member is None:
                break
            yield member

    def _add_zip_member_to_tar(self, zipf: zipfile.ZipFile, member: zipfile.ZipInfo, tar: tarfile.TarFile) -> None:
        """Stream a ZIP entry into a TAR archive without loading the full member into memory."""
        tarinfo = tarfile.TarInfo(name=member.filename)
        tarinfo.mtime = int(datetime(*member.date_time).timestamp())

        if member.is_dir():
            tarinfo.type = tarfile.DIRTYPE
            tarinfo.mode = 0o755
            tar.addfile(tarinfo)
            return

        tarinfo.size = member.file_size
        tarinfo.mode = ((member.external_attr >> 16) & 0o777) or 0o644
        with zipf.open(member, 'r') as source:
            tar.addfile(tarinfo, fileobj=source)

    def _add_rar_member_to_tar(self, rarf: rarfile.RarFile, member: rarfile.RarInfo, tar: tarfile.TarFile) -> None:
        """Stream a RAR entry into a TAR archive without loading the full member into memory."""
        tarinfo = tarfile.TarInfo(name=member.filename)

        if getattr(member, 'mtime', None) is not None:
            tarinfo.mtime = int(member.mtime.timestamp())

        if member.isdir():
            tarinfo.type = tarfile.DIRTYPE
            tarinfo.mode = 0o755
            tar.addfile(tarinfo)
            return

        tarinfo.size = member.file_size
        tarinfo.mode = getattr(member, 'mode', 0o644) or 0o644
        with rarf.open(member.filename, 'r') as source:
            tar.addfile(tarinfo, fileobj=source)

    # ZIP format minimum timestamp (1980-01-01 00:00:00)
    _ZIP_MIN_DATE_TIME = (1980, 1, 1, 0, 0, 0)

    def _add_tar_member_to_zip(self, tar: tarfile.TarFile, member: tarfile.TarInfo, zipf: zipfile.ZipFile) -> None:
        """Stream a TAR entry into a ZIP archive without loading the full member into memory."""
        mtime = member.mtime or 0
        date_time = datetime.fromtimestamp(mtime, tz=timezone.utc).timetuple()[:6]
        if date_time < self._ZIP_MIN_DATE_TIME:
            date_time = self._ZIP_MIN_DATE_TIME

        zipinfo = zipfile.ZipInfo(
            filename=member.name if not member.isdir() else f"{member.name.rstrip('/')}/",
            date_time=date_time,
        )
        zipinfo.external_attr = (member.mode & 0xFFFF) << 16

        if member.isdir():
            zipf.writestr(zipinfo, b'')
            return

        zipinfo.compress_type = zipfile.ZIP_DEFLATED
        with tar.extractfile(member) as source:
            if source is None:
                zipf.writestr(zipinfo, b'')
                return
            with zipf.open(zipinfo, 'w') as dest:
                shutil.copyfileobj(source, dest)
    
    def convert_tar_to_zip(self, output_file: str) -> str:
        """
        Convert a TAR archive to ZIP format.

        Returns:
            Path to the converted ZIP file.

        Raises:
            RuntimeError: If conversion fails.
        """
        with self._open_tar_for_reading() as tar:
            with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for member in self._iter_tar_members(tar):
                    self._add_tar_member_to_zip(tar, member, zipf)
        return output_file

    def convert_zip_to_tar(self, output_file: str, compression_type: str = '') -> str:
        """
        Convert a ZIP archive to TAR format with optional compression.

        Args:
            output_file: Path to the output TAR file.
            compression_type: Compression type for the TAR file ('', 'gz', 'bz2', 'xz', 'zst').

        Returns:
            Path to the converted TAR file.

        Raises:
            RuntimeError: If conversion fails.
        """
        if compression_type not in ('', 'gz', 'bz2', 'xz', 'zst'):
            raise ValueError(f"Unsupported compression type for TAR output: {compression_type}")
        with zipfile.ZipFile(self.input_file, 'r') as zipf:
            with self._open_tar_for_writing(output_file, compression_type) as tar:
                for member in zipf.infolist():
                    self._add_zip_member_to_tar(zipf, member, tar)
        return output_file

    def _convert_tar_to_tar(self, output_file: str) -> str:
        """Re-pack a tar archive with a different compression."""
        compression = self.output_type.lower().removeprefix("tar").lstrip('.')
        with self._open_tar_for_reading() as src:
            with self._open_tar_for_writing(output_file, compression) as dst:
                for member in self._iter_tar_members(src):
                    fileobj = src.extractfile(member)
                    if fileobj is not None:
                        dst.addfile(member, fileobj)
                    else:
                        dst.addfile(member)
        return output_file
    
    def convert_rar_to_tar(self, output_file: str, compression_type: str = '') -> str:
        """
        Convert a RAR archive to TAR format with optional compression.

        Args:
            output_file: Path to the output TAR file.
            compression_type: Compression type for the TAR file ('', 'gz', 'bz2', 'xz', 'zst').

        Returns:
            Path to the converted TAR file.

        Raises:
            RuntimeError: If conversion fails.
        """
        if compression_type not in ('', 'gz', 'bz2', 'xz', 'zst'):
            raise ValueError(f"Unsupported compression type for TAR output: {compression_type}")
        with rarfile.RarFile(self.input_file, 'r') as rarf:
            with self._open_tar_for_writing(output_file, compression_type) as tar:
                for member in rarf.infolist():
                    self._add_rar_member_to_tar(rarf, member, tar)
        return output_file
    
    def convert_rar_to_zip(self, output_file: str) -> str:
        """
        Convert a RAR archive to ZIP format.

        Returns:
            Path to the converted ZIP file.

        Raises:
            RuntimeError: If conversion fails.
        """
        with rarfile.RarFile(self.input_file, 'r') as rarf:
            with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for member in rarf.infolist():
                    file_data = rarf.read(member.filename)
                    zipf.writestr(member.filename, file_data)
        return output_file

    def _safe_extract_7z(self, sz: py7zr.SevenZipFile, dest: str) -> None:
        """Extract a 7z archive, rejecting members with path traversal."""
        for entry in sz.list():
            resolved = os.path.realpath(os.path.join(dest, entry.filename))
            if not resolved.startswith(os.path.realpath(dest) + os.sep) and resolved != os.path.realpath(dest):
                raise ValueError(f"Path traversal detected in 7z member: {entry.filename}")
        # If we get here, all members are safe to extract
        sz.extractall(path=dest)  # nosec B202

    def _safe_extract_tar(self, tar: tarfile.TarFile, dest: str) -> None:
        """Extract a tar archive with path traversal and symlink protection.

        Uses Python 3.12+ ``filter='data'`` which strips ``../``, leading ``/``,
        rejects symlinks/hardlinks that escape the destination, and only permits
        regular files and directories.
        """ 
        tar.extractall(path=dest, filter='data')  # nosec B202

    def convert_7z_to_zip(self, output_file: str) -> str:
        """Convert a 7z archive to ZIP format."""
        with tempfile.TemporaryDirectory(dir=get_settings().tmp_dir) as tmp:
            with py7zr.SevenZipFile(self.input_file, 'r') as sz:
                self._safe_extract_7z(sz, tmp)
            with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, _dirs, files in os.walk(tmp):
                    for fname in files:
                        full = os.path.join(root, fname)
                        arcname = os.path.relpath(full, tmp)
                        zipf.write(full, arcname)
        return output_file

    def convert_7z_to_tar(self, output_file: str, compression_type: str = '') -> str:
        """Convert a 7z archive to TAR format with optional compression."""
        if compression_type not in ('', 'gz', 'bz2', 'xz', 'zst'):
            raise ValueError(f"Unsupported compression type for TAR output: {compression_type}")
        with tempfile.TemporaryDirectory(dir=get_settings().tmp_dir) as tmp:
            with py7zr.SevenZipFile(self.input_file, 'r') as sz:
                self._safe_extract_7z(sz, tmp)
            with self._open_tar_for_writing(output_file, compression_type) as tar:
                for root, _dirs, files in os.walk(tmp):
                    for fname in files:
                        full = os.path.join(root, fname)
                        arcname = os.path.relpath(full, tmp)
                        tar.add(full, arcname=arcname)
        return output_file

    def convert_zip_to_7z(self, output_file: str) -> str:
        """Convert a ZIP archive to 7z format."""
        with zipfile.ZipFile(self.input_file, 'r') as zipf:
            with py7zr.SevenZipFile(output_file, 'w', filters=self._7Z_WRITE_FILTERS) as sz:
                for member in zipf.infolist():
                    if member.is_dir():
                        continue
                    with zipf.open(member, 'r') as source:
                        sz.writef(source, member.filename)
        return output_file

    def convert_tar_to_7z(self, output_file: str) -> str:
        """Convert a TAR archive to 7z format."""
        with tempfile.TemporaryDirectory(dir=get_settings().tmp_dir) as tmp:
            with self._open_tar_for_reading() as tar:
                self._safe_extract_tar(tar, tmp)
            with py7zr.SevenZipFile(output_file, 'w', filters=self._7Z_WRITE_FILTERS) as sz:
                for root, _dirs, files in os.walk(tmp):
                    for fname in files:
                        full = os.path.join(root, fname)
                        arcname = os.path.relpath(full, tmp)
                        sz.write(full, arcname)
        return output_file

    def convert_rar_to_7z(self, output_file: str) -> str:
        """Convert a RAR archive to 7z format."""
        with rarfile.RarFile(self.input_file, 'r') as rarf:
            with py7zr.SevenZipFile(output_file, 'w', filters=self._7Z_WRITE_FILTERS) as sz:
                for member in rarf.infolist():
                    if member.isdir():
                        continue
                    data = rarf.read(member.filename)
                    sz.writef(io.BytesIO(data), member.filename)
        return output_file
    
    def convert(self, overwrite: bool = True, quality: Optional[str] = None) -> list[str]:
        """
        Convert the archive to the output format.

        Args:
            overwrite: Whether to overwrite existing output file (default: True)
            quality: Not applicable for archive conversion, ignored.

        Returns:
            List containing the path to the converted output file.

        Raises:
            FileNotFoundError: If input file doesn't exist.
            ValueError: If the conversion is not supported.
            RuntimeError: If conversion fails.
        """
        if not self.can_convert():
            raise ValueError(
                f"Conversion from {self.input_type} to {self.output_type} is not supported."
            )

        if not os.path.isfile(self.input_file):
            raise FileNotFoundError(f"Input file not found: {self.input_file}")

        # Generate output filename
        input_filename = Path(self.input_file).name.removesuffix(f".{self.input_type}")
        output_file = os.path.join(
            self.output_dir, f"{input_filename}.{self.output_type}"
        )

        # Check if output file exists and overwrite is False
        if not overwrite and os.path.exists(output_file):
            return [output_file]

        if self.input_type.lower().startswith("tar") and self.output_type.lower() == "zip":
            return [self.convert_tar_to_zip(output_file)]

        elif self.input_type.lower() == "zip" and self.output_type.lower().startswith("tar"):
            compression = self.output_type.lower().removeprefix("tar").lstrip('.')
            compression = compression if compression else ''
            return [self.convert_zip_to_tar(output_file, compression)]

        elif self.input_type.lower().startswith("tar") and self.output_type.lower().startswith("tar"):
            return [self._convert_tar_to_tar(output_file)]
        
        elif self.input_type.lower() == "rar" and self.output_type.lower().startswith("tar"):
            compression = self.output_type.lower().removeprefix("tar").lstrip('.')
            compression = compression if compression else ''
            return [self.convert_rar_to_tar(output_file, compression)]
        
        elif self.input_type.lower() == "rar" and self.output_type.lower() == "zip":
            return [self.convert_rar_to_zip(output_file)]

        elif self.input_type.lower() == "rar" and self.output_type.lower() == "7z":
            return [self.convert_rar_to_7z(output_file)]

        elif self.input_type.lower() == "7z" and self.output_type.lower() == "zip":
            return [self.convert_7z_to_zip(output_file)]

        elif self.input_type.lower() == "7z" and self.output_type.lower().startswith("tar"):
            compression = self.output_type.lower().removeprefix("tar").lstrip('.')
            compression = compression if compression else ''
            return [self.convert_7z_to_tar(output_file, compression)]

        elif self.input_type.lower() == "zip" and self.output_type.lower() == "7z":
            return [self.convert_zip_to_7z(output_file)]

        elif self.input_type.lower().startswith("tar") and self.output_type.lower() == "7z":
            return [self.convert_tar_to_7z(output_file)]

        logging.error("Archive conversion is not yet implemented.")
        raise NotImplementedError("Archive conversion is not yet implemented.")