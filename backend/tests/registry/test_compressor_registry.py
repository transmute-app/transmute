import pytest

from compressors import CompressorInterface
from registry.compressor_registry import CompressorRegistry


# ── Stub compressors for isolated testing ────────────────────────────

class _ImageCompressor(CompressorInterface):
    supported_formats = {"png", "jpeg", "webp"}
    formats_with_compression_levels = {"jpeg", "webp"}

    @classmethod
    def can_register(cls) -> bool:
        return True


class _PdfCompressor(CompressorInterface):
    supported_formats = {"pdf"}
    formats_with_compression_levels = {"pdf"}

    @classmethod
    def can_register(cls) -> bool:
        return True


class _VideoCompressor(CompressorInterface):
    supported_formats = {"mp4", "mkv"}

    @classmethod
    def can_register(cls) -> bool:
        return True


class _UnregisterableCompressor(CompressorInterface):
    supported_formats = {"xyz"}

    @classmethod
    def can_register(cls) -> bool:
        return False


@pytest.fixture
def empty_registry():
    """A registry with auto-discovery disabled (no real compressors)."""
    reg = CompressorRegistry.__new__(CompressorRegistry)
    reg.compressors = {}
    reg.format_map = {}
    return reg


@pytest.fixture
def stub_registry(empty_registry):
    """A registry pre-loaded with the stub compressors."""
    empty_registry.register_compressor(_ImageCompressor)
    empty_registry.register_compressor(_PdfCompressor)
    empty_registry.register_compressor(_VideoCompressor)
    return empty_registry


# ── register_compressor ──────────────────────────────────────────────

def test_register_compressor_adds_to_compressors(empty_registry):
    empty_registry.register_compressor(_ImageCompressor)
    assert "_ImageCompressor" in empty_registry.compressors


def test_register_compressor_populates_format_map(empty_registry):
    empty_registry.register_compressor(_ImageCompressor)
    for fmt in _ImageCompressor.supported_formats:
        assert _ImageCompressor in empty_registry.format_map[fmt]


def test_register_compressor_is_idempotent(empty_registry):
    empty_registry.register_compressor(_ImageCompressor)
    empty_registry.register_compressor(_ImageCompressor)
    assert empty_registry.format_map["png"].count(_ImageCompressor) == 1


# ── get_compressor ───────────────────────────────────────────────────

def test_get_compressor_found(stub_registry):
    assert stub_registry.get_compressor("_ImageCompressor") is _ImageCompressor


def test_get_compressor_not_found(stub_registry):
    assert stub_registry.get_compressor("NonExistent") is None


# ── get_formats ──────────────────────────────────────────────────────

def test_get_formats_returns_union(stub_registry):
    fmts = stub_registry.get_formats()
    expected = (
        _ImageCompressor.supported_formats
        | _PdfCompressor.supported_formats
        | _VideoCompressor.supported_formats
    )
    assert fmts == expected


def test_get_formats_empty(empty_registry):
    assert empty_registry.get_formats() == set()


# ── get_normalized_format ────────────────────────────────────────────

def test_normalized_format_alias(stub_registry):
    assert stub_registry.get_normalized_format("jpg") == "jpeg"


def test_normalized_format_passthrough(stub_registry):
    assert stub_registry.get_normalized_format("png") == "png"


def test_normalized_format_lowercased(stub_registry):
    assert stub_registry.get_normalized_format("PNG") == "png"


# ── get_compressors_for_format ───────────────────────────────────────

def test_compressors_for_format(stub_registry):
    result = stub_registry.get_compressors_for_format("png")
    assert _ImageCompressor in result
    assert _PdfCompressor not in result


def test_compressors_for_format_alias(stub_registry):
    # "jpg" should resolve to "jpeg" via alias
    result = stub_registry.get_compressors_for_format("jpg")
    assert _ImageCompressor in result


def test_compressors_for_format_unknown(stub_registry):
    assert stub_registry.get_compressors_for_format("xyz123") == []


# ── get_compressor_for_format ────────────────────────────────────────

def test_compressor_for_format_found(stub_registry):
    compressor = stub_registry.get_compressor_for_format("pdf")
    assert compressor is _PdfCompressor


def test_compressor_for_format_alias(stub_registry):
    compressor = stub_registry.get_compressor_for_format("JPG")
    assert compressor is _ImageCompressor


def test_compressor_for_format_none(stub_registry):
    assert stub_registry.get_compressor_for_format("xyz123") is None


# ── list_compressors ─────────────────────────────────────────────────

def test_list_compressors(stub_registry):
    listing = stub_registry.list_compressors()
    assert "_ImageCompressor" in listing
    assert "_PdfCompressor" in listing
    assert set(listing["_ImageCompressor"]) == _ImageCompressor.supported_formats


def test_list_compressors_empty(empty_registry):
    assert empty_registry.list_compressors() == {}


# ── get_compression_levels_for_format ────────────────────────────────

def test_compression_levels_for_quality_aware_format(stub_registry):
    levels = stub_registry.get_compression_levels_for_format("pdf")
    assert levels == _PdfCompressor.get_compression_levels()


def test_compression_levels_for_format_without_levels(stub_registry):
    # Video compressor declares no formats_with_compression_levels, so no presets.
    assert stub_registry.get_compression_levels_for_format("mp4") == set()


def test_compression_levels_for_unknown_format(stub_registry):
    assert stub_registry.get_compression_levels_for_format("xyz123") == set()


# ── auto-registration semantics ──────────────────────────────────────

def test_skip_unregisterable_skips_classes_returning_false(empty_registry):
    # Simulate the auto-register loop guard manually.
    for cls in (_ImageCompressor, _UnregisterableCompressor):
        if not cls.can_register():
            continue
        empty_registry.register_compressor(cls)
    assert "_ImageCompressor" in empty_registry.compressors
    assert "_UnregisterableCompressor" not in empty_registry.compressors


# ── interface contract ───────────────────────────────────────────────

def test_supports_format_alias_tolerant():
    assert _ImageCompressor.supports_format("jpg") is True
    assert _ImageCompressor.supports_format("JPEG") is True
    assert _ImageCompressor.supports_format("pdf") is False


def test_get_formats_with_compression_levels():
    assert _PdfCompressor.get_formats_with_compression_levels() == {"pdf"}
    assert _VideoCompressor.get_formats_with_compression_levels() == set()
