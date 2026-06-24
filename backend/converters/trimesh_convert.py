import os
from pathlib import Path
from typing import Optional

from core import validate_safe_path

from .converter_interface import ConverterInterface


class TrimeshConverter(ConverterInterface):
    """Convert between 3D mesh interchange formats using the trimesh package.

    trimesh is MIT-licensed and pure Python (numpy-backed, no watermark). It
    loads a mesh and re-exports it in another geometry format. This converter
    only handles geometry interchange; rendering meshes to raster images
    requires an OpenGL context and is intentionally not supported here.
    """

    supported_input_formats: set = {
        'stl',
        'obj',
        'ply',
        'off',
        'glb',
        '3mf',
    }
    supported_output_formats: set = {
        'stl',
        'obj',
        'ply',
        'off',
        'glb',
    }

    def __init__(self, input_file: str, output_dir: str, input_type: str, output_type: str):
        super().__init__(input_file, output_dir, input_type, output_type)

    @staticmethod
    def _load_trimesh():
        try:
            import trimesh
        except ImportError as exc:
            raise RuntimeError(
                "trimesh is not installed; 3D mesh conversion is unavailable."
            ) from exc

        return trimesh

    @classmethod
    def can_register(cls) -> bool:
        try:
            cls._load_trimesh()
            return True
        except RuntimeError:
            return False

    def can_convert(self) -> bool:
        input_fmt = self.input_type.lower()
        output_fmt = self.output_type.lower()

        if input_fmt not in self.supported_input_formats:
            return False
        if output_fmt not in self.supported_output_formats:
            return False
        if input_fmt == output_fmt:
            return False

        return True

    @classmethod
    def get_formats_compatible_with(cls, format_type: str) -> set:
        fmt = format_type.lower()
        if fmt not in cls.supported_input_formats:
            return set()
        return cls.supported_output_formats - {fmt}

    def convert(self, overwrite: bool = True, quality: Optional[str] = None) -> list[str]:
        """Load the input mesh and re-export it in the requested format."""
        del quality

        if not self.can_convert():
            raise ValueError(
                f"Conversion from {self.input_type} to {self.output_type} is not supported."
            )

        if not os.path.isfile(self.input_file):
            raise FileNotFoundError(f"Input file not found: {self.input_file}")

        validate_safe_path(self.input_file)

        trimesh = self._load_trimesh()

        input_filename = Path(self.input_file).stem
        output_file = os.path.join(self.output_dir, f"{input_filename}.{self.output_type}")
        validate_safe_path(output_file)

        if not overwrite and os.path.exists(output_file):
            return [output_file]

        try:
            mesh = trimesh.load(self.input_file, file_type=self.input_type, force='mesh')
        except (ValueError, RuntimeError, FileNotFoundError):
            raise
        except Exception as exc:
            raise RuntimeError(f"Failed to load mesh: {exc}") from exc

        try:
            mesh.export(output_file, file_type=self.output_type)
        except (ValueError, RuntimeError, FileNotFoundError):
            raise
        except Exception as exc:
            raise RuntimeError(f"Mesh export failed: {exc}") from exc

        if not os.path.exists(output_file):
            raise RuntimeError(f"Output file was not created: {output_file}")

        return [output_file]
