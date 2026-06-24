import os
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

from core import validate_safe_path

from .converter_interface import ConverterInterface


class EzdxfConverter(ConverterInterface):
    """Render DXF drawings to PDF, PNG, or SVG using the ezdxf package.

    ezdxf is MIT-licensed and pure Python (no watermark). It reads DXF files
    and renders them through the ``ezdxf.addons.drawing`` pipeline:

    - SVG is produced by the native ``SVGBackend``.
    - PDF and PNG are produced by the ``PyMuPdfBackend`` (backed by PyMuPDF).

    Limitations: DXF only (DWG is not supported), and rendering is 2D
    (3D entities are projected onto the xy-plane).
    """

    supported_input_formats: set = {
        'dxf',
    }
    supported_output_formats: set = {
        'pdf',
        'png',
        'svg',
    }
    formats_with_qualities: set = {
        'png',
    }

    _quality_dpi = {
        'low': 96,
        'medium': 150,
        'high': 300,
    }
    _default_quality = 'medium'

    def __init__(self, input_file: str, output_dir: str, input_type: str, output_type: str):
        super().__init__(input_file, output_dir, input_type, output_type)

    @staticmethod
    def _load_ezdxf():
        try:
            from ezdxf import recover
            from ezdxf.addons.drawing import Frontend, RenderContext, layout
            from ezdxf.addons.drawing.pymupdf import PyMuPdfBackend
            from ezdxf.addons.drawing.svg import SVGBackend
        except ImportError as exc:
            raise RuntimeError(
                "ezdxf is not installed; DXF rendering is unavailable."
            ) from exc

        return SimpleNamespace(
            recover=recover,
            Frontend=Frontend,
            RenderContext=RenderContext,
            layout=layout,
            PyMuPdfBackend=PyMuPdfBackend,
            SVGBackend=SVGBackend,
        )

    @classmethod
    def can_register(cls) -> bool:
        try:
            cls._load_ezdxf()
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
        """Render the input DXF drawing into the requested output format."""
        if not self.can_convert():
            raise ValueError(
                f"Conversion from {self.input_type} to {self.output_type} is not supported."
            )

        if not os.path.isfile(self.input_file):
            raise FileNotFoundError(f"Input file not found: {self.input_file}")

        validate_safe_path(self.input_file)

        deps = self._load_ezdxf()

        input_filename = Path(self.input_file).stem
        output_file = os.path.join(self.output_dir, f"{input_filename}.{self.output_type}")
        validate_safe_path(output_file)

        if not overwrite and os.path.exists(output_file):
            return [output_file]

        try:
            doc, _auditor = deps.recover.readfile(self.input_file)
        except (ValueError, RuntimeError, FileNotFoundError):
            raise
        except Exception as exc:
            raise RuntimeError(f"Failed to read DXF file: {exc}") from exc

        msp = doc.modelspace()

        try:
            if self.output_type == 'svg':
                backend = deps.SVGBackend()
                deps.Frontend(deps.RenderContext(doc), backend).draw_layout(msp)
                svg_string = backend.get_string(deps.layout.Page(0, 0))
                with open(output_file, 'w', encoding='utf-8') as fp:
                    fp.write(svg_string)
            else:
                backend = deps.PyMuPdfBackend()
                deps.Frontend(deps.RenderContext(doc), backend).draw_layout(msp)
                if self.output_type == 'pdf':
                    data = backend.get_pdf_bytes(deps.layout.Page(0, 0))
                else:
                    dpi = self._quality_dpi.get(
                        (quality or self._default_quality),
                        self._quality_dpi[self._default_quality],
                    )
                    data = backend.get_pixmap_bytes(
                        deps.layout.Page(0, 0), fmt='png', dpi=dpi
                    )
                with open(output_file, 'wb') as fp:
                    fp.write(data)
        except (ValueError, RuntimeError, FileNotFoundError):
            raise
        except Exception as exc:
            raise RuntimeError(f"DXF rendering failed: {exc}") from exc

        if not os.path.exists(output_file):
            raise RuntimeError(f"Output file was not created: {output_file}")

        return [output_file]
