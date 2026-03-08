
import argparse
from pathlib import Path
from registry import ConverterRegistry
import json

def get_supported_conversions():
    supported_conversions = list()
    registry = ConverterRegistry(skip_unregisterable=False)
    
    for converter_name, converter_class in registry.converters.items():
        for input_format in converter_class.supported_input_formats:
            for output_format in converter_class.supported_output_formats:
                if input_format != output_format:
                    converter_test = converter_class(input_file="test." + input_format, output_dir=".", input_type=input_format, output_type=output_format)
                    if converter_test.can_convert():
                        supported_conversions.append({
                            "converter_name": converter_name,
                            "input_format": input_format,
                            "output_format": output_format
                        })

    return supported_conversions

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export OpenAPI schema to JSON")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("supported_conversions.json"),
        help="Destination file path (default: ./openapi.json)",
    )
    args = parser.parse_args()

    supported_conversions = get_supported_conversions()
    with open(args.output, "w") as f:
        json.dump(supported_conversions, f, indent=4)
    print(f"Total combinations: {len(supported_conversions)}")
