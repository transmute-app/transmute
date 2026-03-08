from registry import ConverterRegistry

def main():
    registry = ConverterRegistry()

    formats = set()
    for converter in registry.converters.values():
        formats.update(converter.supported_input_formats)
        formats.update(converter.supported_output_formats)

    print(f"Total supported formats: {len(formats)}")

if __name__ == "__main__":
    main()