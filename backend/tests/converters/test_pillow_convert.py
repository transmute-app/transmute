import pytest
from PIL import Image

from converters.pillow_convert import PillowConverter


@pytest.mark.parametrize("output_type", ["png", "apng"])
def test_integer_tiff_to_png_preserves_16_bit_clipping(tmp_path, output_type):
    source = tmp_path / "integer.tiff"
    with Image.new("I", (5, 1)) as image:
        image.putdata([-1, 0, 50_000, 65_535, 100_000])
        image.save(source)

    converter = PillowConverter(str(source), str(tmp_path), "tiff", output_type)
    (output,) = converter.convert()

    with Image.open(output) as image:
        assert image.format == "PNG"
        assert [image.getpixel((x, 0)) for x in range(5)] == [
            0, 0, 50_000, 65_535, 65_535,
        ]
