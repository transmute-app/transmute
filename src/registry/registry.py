import sys
import os
import inspect
from converters import ConverterInterface
import converters


class ConverterRegistry:
    """
    Registry for managing available converters.
    Automatically discovers and registers all converter classes.
    """
    def __init__(self):
        self.converters = {}
        self.format_map = {}  # Maps file format -> list of converter classes
        self._auto_register()
    
    def _auto_register(self):
        """
        Automatically discover and register all converter classes from the converters module.
        """
        # Get all classes from the converters module
        for name, obj in inspect.getmembers(converters, inspect.isclass):
            # Check if it's a subclass of ConverterInterface (but not the interface itself)
            if issubclass(obj, ConverterInterface) and obj is not ConverterInterface:
                self.register_converter(obj)
    
    def register_converter(self, converter_class):
        """
        Register a converter class in the registry.
        
        Args:
            converter_class: The converter class to register
        """
        self.converters[converter_class.__name__] = converter_class
        
        # Map supported formats to this converter
        if hasattr(converter_class, 'supported_formats'):
            for fmt in converter_class.supported_formats:
                if fmt not in self.format_map:
                    self.format_map[fmt] = []
                self.format_map[fmt].append(converter_class)
    
    def get_converter(self, name):
        """
        Retrieve a converter class by name.
        
        Args:
            name: The name of the converter class to retrieve
        
        Returns:
            The converter class if found, else None
        """
        return self.converters.get(name, None)
    
    def get_formats(self):
        """
        Get a set of all supported formats across all registered converters.
        
        Returns:
            Set of supported format strings
        """
        return set(self.format_map.keys())
    
    def get_converters_for_format(self, format_type):
        """
        Get all converters that support a specific file format.
        
        Args:
            format_type: File format (e.g., 'mp4', 'jpg', 'csv')
        
        Returns:
            List of converter classes that support this format
        """
        return self.format_map.get(format_type.lower(), [])
    
    def get_converter_for_conversion(self, input_format, output_format):
        """
        Find the appropriate converter for a specific conversion.
        
        Args:
            input_format: Input file format
            output_format: Output file format
        
        Returns:
            Converter class that supports both formats, or None
        """
        input_converters = set(self.get_converters_for_format(input_format))
        output_converters = set(self.get_converters_for_format(output_format))
        
        # Find converters that support both formats
        compatible = input_converters & output_converters
        
        return compatible.pop() if compatible else None
    
    def list_converters(self):
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
    
    def get_compatible_formats(self, format_type):
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
        format_lower = format_type.lower()
        compatible = set()
        
        # Find all converters that support this format
        converters_for_format = self.get_converters_for_format(format_lower)
        
        # For each converter, determine valid output formats
        for converter_class in converters_for_format:
            if not hasattr(converter_class, 'get_formats_compatible_with'):
                continue
            
            compatible.update(converter_class.get_formats_compatible_with(format_lower))
        
        return compatible
    
    def get_format_compatibility_matrix(self):
        """
        Get a complete compatibility matrix showing which formats can convert to which.
        
        Returns:
            Dictionary mapping each format to its set of compatible output formats
        """
        matrix = {}
        all_formats = set(self.format_map.keys())
        
        for fmt in all_formats:
            matrix[fmt] = self.get_compatible_formats(fmt)
        
        return matrix