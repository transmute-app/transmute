import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

from core import validate_safe_path

from .converter_interface import ConverterInterface

_RENDER_WORKER = os.path.join(os.path.dirname(__file__), "_mesh_render_worker.py")


class MeshRenderConverter(ConverterInterface):
    """Render 3D meshes to raster images (PNG/JPEG/WEBP) using pyrender.

    pyrender performs offscreen OpenGL rendering. On headless Linux this uses
    OSMesa (software Mesa) via ``PYOPENGL_PLATFORM=osmesa``; no display server
    is required. This converter only produces preview images -- mesh-to-mesh
    geometry interchange is handled separately by ``TrimeshConverter``.

    Rendering runs in a subprocess (``_mesh_render_worker.py``) so that native
    OpenGL context creation never happens on a background worker thread (which
    aborts on macOS) and so a native renderer crash is isolated from the API.
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
        'png',
        'jpeg',
        'webp',
    }
    formats_with_qualities: set = {
        'png',
        'jpeg',
        'webp',
    }

    _quality_size = {
        'low': 512,
        'medium': 1024,
        'high': 2048,
    }
    _default_quality = 'medium'

    def __init__(self, input_file: str, output_dir: str, input_type: str, output_type: str):
        super().__init__(input_file, output_dir, input_type, output_type)

    @staticmethod
    def _load_render_deps():
        try:
            import numpy as np
            import pyrender
            import trimesh
        except ImportError as exc:
            raise RuntimeError(
                "pyrender/trimesh are not installed; 3D mesh rendering is unavailable."
            ) from exc

        return SimpleNamespace(np=np, pyrender=pyrender, trimesh=trimesh)

    @classmethod
    def can_register(cls) -> bool:
        try:
            cls._load_render_deps()
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

        return True

    @classmethod
    def get_formats_compatible_with(cls, format_type: str) -> set:
        fmt = format_type.lower()
        if fmt not in cls.supported_input_formats:
            return set()
        return cls.supported_output_formats.copy()

    def convert(self, overwrite: bool = True, quality: Optional[str] = None) -> list[str]:
        """Render the input mesh to a raster image."""
        if not self.can_convert():
            raise ValueError(
                f"Conversion from {self.input_type} to {self.output_type} is not supported."
            )

        if not os.path.isfile(self.input_file):
            raise FileNotFoundError(f"Input file not found: {self.input_file}")

        validate_safe_path(self.input_file)

        input_filename = Path(self.input_file).stem
        output_file = os.path.join(self.output_dir, f"{input_filename}.{self.output_type}")
        validate_safe_path(output_file)

        if not overwrite and os.path.exists(output_file):
            return [output_file]

        size = self._quality_size.get(
            (quality or self._default_quality),
            self._quality_size[self._default_quality],
        )

        # Render in a subprocess: native OpenGL context creation must not run on
        # a background worker thread (aborts on macOS), and a native crash is
        # contained in the child instead of killing the API server.
        proc = subprocess.run(
            [
                sys.executable,
                _RENDER_WORKER,
                self.input_file,
                self.input_type,
                output_file,
                self.output_type,
                str(size),
            ],
            capture_output=True,
            text=True,
        )

        if proc.returncode != 0:
            detail = proc.stderr.strip() or f"renderer exited with code {proc.returncode}"
            raise RuntimeError(f"Mesh rendering failed: {detail}")

        if not os.path.exists(output_file):
            raise RuntimeError(f"Output file was not created: {output_file}")

        return [output_file]
