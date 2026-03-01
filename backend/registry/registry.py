import inspect
from typing import Type
from core import media_type_aliases
from converters import ConverterInterface
import converters


class ConverterRegistry:
    """
    Registry for managing available converters.
    Automatically discovers and registers all converter classes.
    """
    def __init__(self) -> None:
        self.converters = {}
        self.input_format_map = {}  # Maps input format -> list of converter classes
        self.output_format_map = {}  # Maps output format -> list of converter classes
        self._auto_register()
    
    def _auto_register(self) -> None:
        """
        Automatically discover and register all converter classes from the converters module.
        """
        # Get all classes from the converters module
        for name, obj in inspect.getmembers(converters, inspect.isclass):
            # Check if it's a subclass of ConverterInterface (but not the interface itself)
            # And also check if it can be registered (e.g., required dependencies are met)
            if issubclass(obj, ConverterInterface) and \
                obj is not ConverterInterface and \
                obj.can_register():
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
        return set(self.input_format_map.keys()) | set(self.output_format_map.keys())
    
    def get_normalized_format(self, format_type) -> str:
        """
        Get the normalized format name for a given format type, using media type aliases.
        
        Args:
            format_type: The input format type (e.g., 'jpg', 'jpeg', 'mp4')
            
        Returns:
            The normalized format name if found, else the original format type
        """
        return media_type_aliases.get(format_type.lower(), format_type.lower())
    
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
        
        return compatible.pop() if compatible else None
    
    def list_converters(self) -> dict[str, list[str]] :
        """
        List all registered converters with their supported formats.
        
        Returns:
            Dictionary mapping converter names to their supported formats
        """
        result = {}
        for name, converter_class in self.converters.items():
            if hasattr(converter_class, 'supported_formats'):
                result[name] = list(converter_class.supported_formats)
            else:
                result[name] = []
        return result
    
    def get_compatible_formats(self, format_type) -> set[str]:
        """
        Get all formats compatible with the given format.
        
        A format is considered compatible if there exists a converter that
        supports both the given format and the compatible format, AND the
        conversion is actually valid in that direction.
        
        Args:
            format_type: File format (e.g., 'jpg', 'mp4', 'csv')
        
        Returns:
            Set of compatible format strings
        """
        normalized_format = self.get_normalized_format(format_type)
        compatible = set()
        
        # Find all converters that support this format
        converters_for_format = self.get_converters_for_input_format(normalized_format)
        
        # For each converter, determine valid output formats
        for converter_class in converters_for_format:
            if not hasattr(converter_class, 'get_formats_compatible_with'):
                continue
            
            compatible.update(converter_class.get_formats_compatible_with(normalized_format))
        
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
            matrix[normalized_fmt] = self.get_compatible_formats(normalized_fmt)
        
        return matrix


# Shared singleton — import this instead of instantiating ConverterRegistry() directly.
registry = ConverterRegistry()