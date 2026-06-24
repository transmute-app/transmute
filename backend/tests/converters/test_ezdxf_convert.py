import shutil
from pathlib import Path

import pytest

from converters.ezdxf_convert import EzdxfConverter

ezdxf = pytest.importorskip("ezdxf")

SAMPLE_DXF = Path(__file__).resolve().parents[3] / "assets" / "samples" / "dxf.dxf"


def _stage_input(settings, ext: str) -> Path:
    input_name = "a" * 32
    input_file = settings.upload_dir / f"{input_name}.{ext}"
    shutil.copyfile(SAMPLE_DXF, input_file)
    return input_file


@pytest.mark.parametrize("output_type", ["svg", "pdf", "png"])
def test_convert_dxf_to_supported_formats(output_type, safe_path_test_settings):
    input_file = _stage_input(safe_path_test_settings, "dxf")
    output_file = safe_path_test_settings.output_dir / f"{'a' * 32}.{output_type}"

    converter = EzdxfConverter(
        input_file=str(input_file),
        output_dir=str(safe_path_test_settings.output_dir),
        input_type="dxf",
        output_type=output_type,
    )

    assert converter.convert() == [str(output_file)]
    assert output_file.exists()
    assert output_file.stat().st_size > 0


def test_png_quality_affects_output_size(safe_path_test_settings):
    input_file = _stage_input(safe_path_test_settings, "dxf")

    low = EzdxfConverter(
        input_file=str(input_file),
        output_dir=str(safe_path_test_settings.output_dir),
        input_type="dxf",
        output_type="png",
    ).convert(quality="low")
    low_size = Path(low[0]).stat().st_size

    high = EzdxfConverter(
        input_file=str(input_file),
        output_dir=str(safe_path_test_settings.output_dir),
        input_type="dxf",
        output_type="png",
    ).convert(quality="high")
    high_size = Path(high[0]).stat().st_size

    assert high_size > low_size


def test_can_register_false_when_dependency_missing(monkeypatch):
    def raise_runtime_error():
        raise RuntimeError("missing dependency")

    monkeypatch.setattr(
        EzdxfConverter,
        "_load_ezdxf",
        staticmethod(raise_runtime_error),
    )

    assert EzdxfConverter.can_register() is False


def test_can_convert_matrix(safe_path_test_settings):
    def make(input_type, output_type):
        return EzdxfConverter(
            input_file=str(safe_path_test_settings.upload_dir / f"{'a' * 32}.{input_type}"),
            output_dir=str(safe_path_test_settings.output_dir),
            input_type=input_type,
            output_type=output_type,
        )

    assert make("dxf", "svg").can_convert() is True
    assert make("dxf", "pdf").can_convert() is True
    assert make("dxf", "png").can_convert() is True
    assert make("dxf", "dwg").can_convert() is False
    assert make("stl", "svg").can_convert() is False


def test_get_formats_compatible_with():
    assert EzdxfConverter.get_formats_compatible_with("dxf") == {"pdf", "png", "svg"}
    assert EzdxfConverter.get_formats_compatible_with("stl") == set()


def test_get_formats_with_quality_options():
    assert EzdxfConverter.get_formats_with_quality_options() == {"png"}
