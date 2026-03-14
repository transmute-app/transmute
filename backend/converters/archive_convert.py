import io
import os
import logging
import tarfile
import zipfile
from pathlib import Path
from typing import Optional

import pyzstd

from .converter_interface import ConverterInterface


logger = logging.getLogger(__name__)

class ArchiveConverter(ConverterInterface):
    """
    Converter for repacking between archive formats like ZIP and TAR.GZ.
    """

    supported_input_formats: set = {
        'zip',
        'tar',
        'tar.gz',
        'tar.bz2',
        'tar.xz',
        'tar.zst',
    }
    supported_output_formats: set = {
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
        Check if the converter can be registered based on supported formats.

        Returns:
            True if the converter can be registered, False otherwise.
        """
        return True  # This converter is not registered in the registry and is only used for testing purposes

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

    def _open_tar_for_reading(self) -> tarfile.TarFile:
        """Open the input tar archive, decompressing zstandard if needed."""
        if self.input_type.lower() == 'tar.zst':
            data = pyzstd.decompress(Path(self.input_file).read_bytes())
            return tarfile.open(fileobj=io.BytesIO(data), mode='r')
        return tarfile.open(self.input_file, 'r:*')
    
    def convert_tar_to_zip(self, output_file: str) -> str:
        """
        Convert a TAR archive to ZIP format.

        Returns:
            Path to the converted ZIP file.

        Raises:
            RuntimeError: If conversion fails.
        """
        tar = self._open_tar_for_reading()
        with tar:
            with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for member in tar.getmembers():
                    fileobj = tar.extractfile(member)
                    if fileobj is not None:
                        zipf.writestr(member.name, fileobj.read())
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
        if compression_type == 'zst':
            return self._convert_zip_to_tar_zst(output_file)
        if compression_type in ('gz', 'bz2', 'xz'):
            tar_mode = f"w:{compression_type}"
        else:
            tar_mode = 'w'
        with zipfile.ZipFile(self.input_file, 'r') as zipf:
            with tarfile.open(output_file, tar_mode) as tar:
                for member in zipf.infolist():
                    file_data = zipf.read(member.filename)
                    tarinfo = tarfile.TarInfo(name=member.filename)
                    tarinfo.size = len(file_data)
                    tar.addfile(tarinfo, fileobj=io.BytesIO(file_data))
        return output_file

    def _convert_zip_to_tar_zst(self, output_file: str) -> str:
        """Write a ZIP as a zstandard-compressed tar archive."""
        buf = io.BytesIO()
        with zipfile.ZipFile(self.input_file, 'r') as zipf:
            with tarfile.open(fileobj=buf, mode='w') as tar:
                for member in zipf.infolist():
                    file_data = zipf.read(member.filename)
                    tarinfo = tarfile.TarInfo(name=member.filename)
                    tarinfo.size = len(file_data)
                    tar.addfile(tarinfo, fileobj=io.BytesIO(file_data))
        with open(output_file, 'wb') as f:
            f.write(pyzstd.compress(buf.getvalue()))
        return output_file

    def _convert_tar_to_tar(self, output_file: str) -> str:
        """Re-pack a tar archive with a different compression."""
        compression = self.output_type.lower().removeprefix("tar").lstrip('.')

        # Read the source tar (handles zst transparently)
        src = self._open_tar_for_reading()

        if compression == 'zst':
            buf = io.BytesIO()
            with src, tarfile.open(fileobj=buf, mode='w') as dst:
                for member in src.getmembers():
                    fileobj = src.extractfile(member)
                    if fileobj is not None:
                        dst.addfile(member, fileobj)
                    else:
                        dst.addfile(member)
            with open(output_file, 'wb') as f:
                f.write(pyzstd.compress(buf.getvalue()))
        else:
            tar_mode = f"w:{compression}" if compression else 'w'
            with src, tarfile.open(output_file, tar_mode) as dst:
                for member in src.getmembers():
                    fileobj = src.extractfile(member)
                    if fileobj is not None:
                        dst.addfile(member, fileobj)
                    else:
                        dst.addfile(member)
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

        logging.error("Archive conversion is not yet implemented.")
        raise NotImplementedError("Archive conversion is not yet implemented.")