import inspect
from typing import Type
from core import media_type_aliases
from converters import ConverterInterface
import converters


WEBVIDEO_FORMAT = "webvideo"
WEBVIDEO_BASE_FORMAT = "mp4"
WEBAUDIO_FORMAT = "webaudio"
WEBAUDIO_BASE_FORMAT = "m4a"

# Synthetic input media types produced by URL downloaders (e.g. yt-dlp), each
# mapped to the real format they pass through to. Conversions advertised for
# a web alias are the same as those advertised for its base format, plus a
# trivial passthrough to the base format itself.
WEB_ALIAS_BASE_FORMATS: dict[str, str] = {
    WEBVIDEO_FORMAT: WEBVIDEO_BASE_FORMAT,
    WEBAUDIO_FORMAT: WEBAUDIO_BASE_FORMAT,
}

_PYMUPDF_IMAGE_TO_PDF_INPUTS = {
    'png',
    'jpeg',
    'webp',
    'tiff',
    'bmp',
    'gif',
    'ppm',
    'pgm',
    'pbm',
    'tga',
    'jp2',
    'avif',
    'jxl',
    'ico',
    'dib',
    'pcx',
    'sgi',
    'pnm',
    'heif',
    'heic',
}


class ConverterRegistry:
    """
    Registry for managing available converters.
    Automatically discovers and registers all converter classes.
    """
    def __init__(self, skip_unregisterable: bool = True) -> None:
        self.converters = {}
        self.input_format_map = {}  # Maps input format -> list of converter classes
        self.output_format_map = {}  # Maps output format -> list of converter classes
        self._auto_register(skip_unregisterable)
    
    def _auto_register(self, skip_unregisterable: bool) -> None:
        """
        Automatically discover and register all converter classes from the converters module.
        """
        # Get all classes from the converters module
        for name, obj in inspect.getmembers(converters, inspect.isclass):
            # Check if it's a subclass of ConverterInterface (but not the interface itself)
            # And also check if it can be registered (e.g., required dependencies are met)
            if issubclass(obj, ConverterInterface) and \
                obj is not ConverterInterface:
                if skip_unregisterable and not obj.can_register():
                    continue
                self.register_converter(obj)
    
    def register_converter(self, converter_class) -> None:
        """
        Register a converter class in the registry.
        
        Args:
            converter_class: The converter class to register
        """
        self.converters[converter_class.__name__] = converter_class
        
        # Map supported formats to this converter
        if hasattr(converter_class, 'supported_input_formats'):
            for fmt in converter_class.supported_input_formats:
                if fmt not in self.input_format_map:
                    self.input_format_map[fmt] = []
                self.input_format_map[fmt].append(converter_class)
                for alias_format, base_format in WEB_ALIAS_BASE_FORMATS.items():
                    if fmt == base_format:
                        if alias_format not in self.input_format_map:
                            self.input_format_map[alias_format] = []
                        self.input_format_map[alias_format].append(converter_class)
        # Map supported formats to this converter
        if hasattr(converter_class, 'supported_output_formats'):
            for fmt in converter_class.supported_output_formats:
                if fmt not in self.output_format_map:
                    self.output_format_map[fmt] = []
                self.output_format_map[fmt].append(converter_class)
    
    def get_converter(self, name) -> Type[ConverterInterface] | None:
        """
        Retrieve a converter class by name.
        
        Args:
            name: The name of the converter class to retrieve
        
        Returns:
            The converter class if found, else None
        """
        return self.converters.get(name, None)
    
    def get_formats(self) -> set[str]:
        """
        Get a set of all supported formats across all registered converters.
        
        Returns:
            Set of supported format strings
        """
        formats: set[str] = set()
        for converter_class in self.converters.values():
            formats.update(getattr(converter_class, 'supported_input_formats', set()))
            formats.update(getattr(converter_class, 'supported_output_formats', set()))
        return formats
    
    def get_normalized_format(self, format_type) -> str:
        """
        Get the normalized format name for a given format type, using media type aliases.
        
        Compound types like ``p7m/pdf`` are normalized to their base (``p7m``)
        when no explicit alias exists, so the registry can look up converters
        by the container format.
        
        Args:
            format_type: The input format type (e.g., 'jpg', 'jpeg', 'mp4')
            
        Returns:
            The normalized format name if found, else the original format type
        """
        lower = format_type.lower()
        normalized = media_type_aliases.get(lower, lower)
        # Compound types like p7m/pdf: normalize to the base format for
        # converter lookup, but only when no explicit alias exists.
        if normalized == lower and '/' in lower and not lower.startswith('pdf/'):
            return lower.split('/')[0]
        return normalized
    
    def get_converters_for_input_format(self, format_type) -> list[Type[ConverterInterface]]:
        """
        Get all converters that support a specific input file format.
        
        Args:
            format_type: File format (e.g., 'mp4', 'jpg', 'csv')
        
        Returns:
            List of converter classes that support this input format
        """
        normalized_format = self.get_normalized_format(format_type)
        return self.input_format_map.get(normalized_format, [])
    
    def get_converters_for_output_format(self, format_type) -> list[Type[ConverterInterface]]:
        """
        Get all converters that support a specific output file format.
        
        Args:
            format_type: File format (e.g., 'mp4', 'jpg', 'csv')
        
        Returns:
            List of converter classes that support this output format
        """
        normalized_format = self.get_normalized_format(format_type)
        return self.output_format_map.get(normalized_format, [])
    
    def get_converter_for_conversion(self, input_format, output_format) -> Type[ConverterInterface] | None:
        """
        Find the appropriate converter for a specific conversion.
        
        Args:
            input_format: Input file format
            output_format: Output file format
        
        Returns:
            Converter class that supports both formats, or None
        """
        normalized_input = self.get_normalized_format(input_format)
        normalized_output = self.get_normalized_format(output_format)
        input_converters = set(self.get_converters_for_input_format(normalized_input))
        output_converters = set(self.get_converters_for_output_format(normalized_output))
        
        # Find converters that support both formats
        compatible = input_converters & output_converters
        if compatible:
            directionally_compatible = {
                converter
                for converter in compatible
                if normalized_output in converter.get_formats_compatible_with(input_format)
            }
            candidates = directionally_compatible or compatible
            preferred = self._get_preferred_converter(candidates, normalized_input, normalized_output)
            if preferred is not None:
                return preferred

        # Fallback: check if any input converter dynamically supports this
        # output (e.g. PKCS7Converter for compound types like "p7m/pdf").
        for converter in input_converters:
            if normalized_output in converter.get_formats_compatible_with(input_format):
                return converter

        return None

    @staticmethod
    def _get_preferred_converter(
        compatible: set[Type[ConverterInterface]],
        normalized_input: str,
        normalized_output: str,
    ) -> Type[ConverterInterface] | None:
        """Choose a deterministic converter when multiple classes match."""
        if normalized_output == 'pdf' and normalized_input.startswith('pdf'):
            for converter in compatible:
                if converter.__name__ == 'PyMuPDFConverter':
                    return converter

        if normalized_output == 'pdf' and normalized_input in _PYMUPDF_IMAGE_TO_PDF_INPUTS:
            for converter in compatible:
                if converter.__name__ == 'PyMuPDFConverter':
                    return converter

        return sorted(compatible, key=lambda converter: converter.__name__)[0]
    
    def list_converters(self) -> dict[str, list[str]] :
        """
        List all registered converters with their supported formats.
        
        Returns:
            Dictionary mapping converter names to their supported formats
        """
        result = {}
        for name, converter_class in self.converters.items():
            if hasattr(converter_class, 'supported_input_formats'):
                result[name] = list(converter_class.supported_input_formats)
            else:
                result[name] = []
        return result
    
    def get_compatible_formats_and_qualities(self, format_type) -> dict[str, set[str]]:
        """
        Get all formats compatible with the given format.
        
        A format is considered compatible if there exists a converter that
        supports both the given format and the compatible format, AND the
        conversion is actually valid in that direction.
        
        Args:
            format_type: File format (e.g., 'jpg', 'mp4', 'csv')
        
        Returns:
            Dictionary mapping compatible format strings to their available quality options
        """
        normalized_format = self.get_normalized_format(format_type)
        alias_base_format = WEB_ALIAS_BASE_FORMATS.get(normalized_format)
        compatibility_input_format = alias_base_format if alias_base_format else format_type
        compatible = dict()
        
        # Find all converters that support this format
        converters_for_format = self.get_converters_for_input_format(normalized_format)
        
        # For each converter, determine valid output formats.
        # Pass the original format_type so converters with compound-type
        # awareness (e.g. PKCS7Converter for "p7m/pdf") can inspect it.
        for converter_class in converters_for_format:
            if not hasattr(converter_class, 'get_formats_compatible_with'):
                continue
            
            for compatible_format in converter_class.get_formats_compatible_with(compatibility_input_format):
                if compatible_format not in compatible:
                    compatible[compatible_format] = set()
                if compatible_format in converter_class.get_formats_with_quality_options():
                    compatible[compatible_format].update(converter_class.get_quality_options())

            if (
                alias_base_format is not None
                and alias_base_format in getattr(converter_class, 'supported_output_formats', set())
            ):
                compatible.setdefault(alias_base_format, set())
                if alias_base_format in converter_class.get_formats_with_quality_options():
                    compatible[alias_base_format].update(converter_class.get_quality_options())
        return compatible
    
    def get_format_compatibility_matrix(self) -> dict[str, set[str]]:
        """
        Get a complete compatibility matrix showing which formats can convert to which.
        
        Returns:
            Dictionary mapping each format to its set of compatible output formats
        """
        matrix = {}
        all_formats = set(self.input_format_map.keys()) | set(self.output_format_map.keys())
        
        for fmt in all_formats:
            normalized_fmt = self.get_normalized_format(fmt)
            matrix[normalized_fmt] = self.get_compatible_formats_and_qualities(normalized_fmt).keys()
        
        return matrix


# Shared singleton — import this instead of instantiating ConverterRegistry() directly.
registry = ConverterRegistry()