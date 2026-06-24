import shutil
from pathlib import Path

import pytest

from converters.trimesh_convert import TrimeshConverter

trimesh = pytest.importorskip("trimesh")

SAMPLES_DIR = Path(__file__).resolve().parents[3] / "assets" / "samples"


def _stage_input(settings, sample_name: str, ext: str) -> Path:
    input_name = "a" * 32
    input_file = settings.upload_dir / f"{input_name}.{ext}"
    shutil.copyfile(SAMPLES_DIR / sample_name, input_file)
    return input_file


@pytest.mark.parametrize(
    "sample_name,input_type,output_type",
    [
        ("stl.stl", "stl", "obj"),
        ("stl.stl", "stl", "ply"),
        ("stl.stl", "stl", "glb"),
        ("obj.obj", "obj", "stl"),
    ],
)
def test_convert_mesh_interchange(sample_name, input_type, output_type, safe_path_test_settings):
    input_file = _stage_input(safe_path_test_settings, sample_name, input_type)
    output_file = safe_path_test_settings.output_dir / f"{'a' * 32}.{output_type}"

    converter = TrimeshConverter(
        input_file=str(input_file),
        output_dir=str(safe_path_test_settings.output_dir),
        input_type=input_type,
        output_type=output_type,
    )

    assert converter.convert() == [str(output_file)]
    assert output_file.exists()
    assert output_file.stat().st_size > 0


def test_can_register_false_when_dependency_missing(monkeypatch):
    def raise_runtime_error():
        raise RuntimeError("missing dependency")

    monkeypatch.setattr(
        TrimeshConverter,
        "_load_trimesh",
        staticmethod(raise_runtime_error),
    )

    assert TrimeshConverter.can_register() is False


def test_can_convert_matrix(safe_path_test_settings):
    def make(input_type, output_type):
        return TrimeshConverter(
            input_file=str(safe_path_test_settings.upload_dir / f"{'a' * 32}.{input_type}"),
            output_dir=str(safe_path_test_settings.output_dir),
            input_type=input_type,
            output_type=output_type,
        )

    assert make("stl", "obj").can_convert() is True
    assert make("glb", "obj").can_convert() is True
    assert make("stl", "stl").can_convert() is False
    assert make("obj", "dxf").can_convert() is False
    assert make("dxf", "obj").can_convert() is False


def test_get_formats_compatible_with():
    assert TrimeshConverter.get_formats_compatible_with("stl") == {"obj", "ply", "off", "glb"}
    assert TrimeshConverter.get_formats_compatible_with("glb") == {"stl", "obj", "ply", "off"}
    assert TrimeshConverter.get_formats_compatible_with("dxf") == set()
