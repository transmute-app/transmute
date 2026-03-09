# Converters

This package contains the concrete file conversion implementations used by Transmute.

## Purpose

- Define converter classes for each supported toolchain or format family.
- Normalize conversion behavior behind a common interface.
- Expose converter classes for automatic discovery by the registry.

## Contents

- `converter_interface.py`: base contract for all converter implementations.
- `*_convert.py`: concrete converters backed by tools such as FFmpeg, Pillow, Pandas, LibreOffice, PyMuPDF, and others.
- `__init__.py`: re-exports converter classes so the registry can inspect the package and auto-register supported converters.

## How To Work In This Folder

- Implement new converters as subclasses of `ConverterInterface`.
- Define `supported_input_formats` and `supported_output_formats` on each converter class.
- Override `can_register()` when a converter depends on a non-Python binary or optional runtime dependency.
- Keep conversion logic inside the converter class rather than branching on tool type elsewhere in the app.

## Practical Guidelines

- Make the converter responsible for filesystem output creation under the provided output directory.
- Normalize formats using the interface's existing alias handling instead of duplicating extension mapping logic.
- Return a list of produced output paths from `convert()`, even when the converter usually emits one file.
- Avoid importing the registry from converter modules to prevent circular dependencies.
- If a converter has unusual limitations, encode them in `can_convert()` or `get_formats_compatible_with()`.

## Typical Workflow

1. Create a new `*_convert.py` module with a `ConverterInterface` subclass.
2. Add the class to `__init__.py` so registry auto-discovery can see it.
3. Implement `can_convert()` and `convert()`.
4. Implement `can_register()` if external binaries or optional libraries are required.
5. Add tests for the new format mapping or conversion behavior where feasible.
