import inspect
from typing import Type

from core import media_type_aliases
from compressors import CompressorInterface
import compressors


class CompressorRegistry:
    """
    Registry for managing available compressors.

    Compressors reduce the size of a file without changing its format, so
    lookup is keyed by a single media type rather than an input/output pair.
    Compressor classes are auto-discovered from the ``compressors`` package
    via reflection over ``CompressorInterface`` subclasses.
    """

    def __init__(self, skip_unregisterable: bool = True) -> None:
        self.compressors: dict[str, Type[CompressorInterface]] = {}
        self.format_map: dict[str, list[Type[CompressorInterface]]] = {}
        self._auto_register(skip_unregisterable)

    def _auto_register(self, skip_unregisterable: bool) -> None:
        """
        Automatically discover and register all compressor classes from the
        ``compressors`` package.
        """
        for _name, obj in inspect.getmembers(compressors, inspect.isclass):
            if issubclass(obj, CompressorInterface) and obj is not CompressorInterface:
                if skip_unregisterable and not obj.can_register():
                    continue
                self.register_compressor(obj)

    def register_compressor(self, compressor_class: Type[CompressorInterface]) -> None:
        """
        Register a compressor class in the registry.
        """
        self.compressors[compressor_class.__name__] = compressor_class

        if hasattr(compressor_class, 'supported_formats'):
            for fmt in compressor_class.supported_formats:
                bucket = self.format_map.setdefault(fmt, [])
                if compressor_class not in bucket:
                    bucket.append(compressor_class)

    def get_compressor(self, name: str) -> Type[CompressorInterface] | None:
        """
        Retrieve a compressor class by class name.
        """
        return self.compressors.get(name, None)

    def get_formats(self) -> set[str]:
        """
        Get the union of all formats supported across registered compressors.
        """
        formats: set[str] = set()
        for compressor_class in self.compressors.values():
            formats.update(getattr(compressor_class, 'supported_formats', set()))
        return formats

    def get_normalized_format(self, format_type: str) -> str:
        """
        Normalize a format string using the shared media type alias map.
        """
        lower = format_type.lower()
        return media_type_aliases.get(lower, lower)

    def get_compressors_for_format(self, format_type: str) -> list[Type[CompressorInterface]]:
        """
        Get all compressors that support the given media type.
        """
        normalized = self.get_normalized_format(format_type)
        return list(self.format_map.get(normalized, []))

    def get_compressor_for_format(self, format_type: str) -> Type[CompressorInterface] | None:
        """
        Find a compressor for the given media type.

        Returns the first registered compressor that supports the format,
        or ``None`` when no compressor is available for it.
        """
        compressors_for_format = self.get_compressors_for_format(format_type)
        if not compressors_for_format:
            return None
        return compressors_for_format[0]

    def list_compressors(self) -> dict[str, list[str]]:
        """
        List all registered compressors with the formats they support.
        """
        result: dict[str, list[str]] = {}
        for name, compressor_class in self.compressors.items():
            result[name] = list(getattr(compressor_class, 'supported_formats', set()))
        return result

    def get_compression_levels_for_format(self, format_type: str) -> set[str]:
        """
        Get the union of compression-level presets offered by compressors that
        support the given format. Empty when the format has no compressor that
        honors a compression-level argument.
        """
        normalized = self.get_normalized_format(format_type)
        levels: set[str] = set()
        for compressor_class in self.format_map.get(normalized, []):
            if normalized in compressor_class.get_formats_with_compression_levels():
                levels.update(compressor_class.get_compression_levels())
        return levels


# Shared singleton — import this instead of instantiating CompressorRegistry() directly.
compressor_registry = CompressorRegistry()
