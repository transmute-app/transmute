import shutil
from pathlib import Path

import pytest

from converters.mesh_render_convert import MeshRenderConverter

pytest.importorskip("pyrender")
pytest.importorskip("trimesh")

SAMPLES_DIR = Path(__file__).resolve().parents[3] / "assets" / "samples"


def _render_available() -> bool:
    """Probe whether an offscreen OpenGL context can be created in this env."""
    try:
        import pyrender

        renderer = pyrender.OffscreenRenderer(16, 16)
        renderer.delete()
        return True
    except Exception:
        return False


requires_gl = pytest.mark.skipif(
    not _render_available(),
    reason="No offscreen OpenGL context available (needs OSMesa/EGL or a display).",
)


def _stage_input(settings, sample_name: str, ext: str) -> Path:
    input_name = "a" * 32
    input_file = settings.upload_dir / f"{input_name}.{ext}"
    shutil.copyfile(SAMPLES_DIR / sample_name, input_file)
    return input_file


@requires_gl
@pytest.mark.parametrize(
    "sample_name,input_type,output_type",
    [
        ("stl.stl", "stl", "png"),
        ("stl.stl", "stl", "jpeg"),
        ("stl.stl", "stl", "webp"),
        ("obj.obj", "obj", "png"),
    ],
)
def test_render_mesh_to_image(sample_name, input_type, output_type, safe_path_test_settings):
    input_file = _stage_input(safe_path_test_settings, sample_name, input_type)
    output_file = safe_path_test_settings.output_dir / f"{'a' * 32}.{output_type}"

    converter = MeshRenderConverter(
        input_file=str(input_file),
        output_dir=str(safe_path_test_settings.output_dir),
        input_type=input_type,
        output_type=output_type,
    )

    assert converter.convert() == [str(output_file)]
    assert output_file.exists()
    assert output_file.stat().st_size > 0

    from PIL import Image

    with Image.open(output_file) as img:
        assert img.size == (1024, 1024)  # default medium quality


@requires_gl
def test_quality_affects_resolution(safe_path_test_settings):
    input_file = _stage_input(safe_path_test_settings, "stl.stl", "stl")

    from PIL import Image

    low = MeshRenderConverter(
        input_file=str(input_file),
        output_dir=str(safe_path_test_settings.output_dir),
        input_type="stl",
        output_type="png",
    ).convert(quality="low")
    with Image.open(low[0]) as img:
        assert img.size == (512, 512)

    high = MeshRenderConverter(
        input_file=str(input_file),
        output_dir=str(safe_path_test_settings.output_dir),
        input_type="stl",
        output_type="png",
    ).convert(quality="high")
    with Image.open(high[0]) as img:
        assert img.size == (2048, 2048)


def test_can_register_false_when_dependency_missing(monkeypatch):
    def raise_runtime_error():
        raise RuntimeError("missing dependency")

    monkeypatch.setattr(
        MeshRenderConverter,
        "_load_render_deps",
        staticmethod(raise_runtime_error),
    )

    assert MeshRenderConverter.can_register() is False


def test_can_convert_matrix(safe_path_test_settings):
    def make(input_type, output_type):
        return MeshRenderConverter(
            input_file=str(safe_path_test_settings.upload_dir / f"{'a' * 32}.{input_type}"),
            output_dir=str(safe_path_test_settings.output_dir),
            input_type=input_type,
            output_type=output_type,
        )

    assert make("stl", "png").can_convert() is True
    assert make("obj", "jpeg").can_convert() is True
    assert make("glb", "webp").can_convert() is True
    assert make("stl", "obj").can_convert() is False
    assert make("dxf", "png").can_convert() is False


def test_get_formats_compatible_with():
    assert MeshRenderConverter.get_formats_compatible_with("stl") == {"png", "jpeg", "webp"}
    assert MeshRenderConverter.get_formats_compatible_with("dxf") == set()
