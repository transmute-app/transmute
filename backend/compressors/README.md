# Compressors

This package contains the concrete file compression implementations used by Transmute.

## Purpose

- Define compressor classes for each supported toolchain or format family.
- Reduce the size of a file without changing its format.
- Expose compressor classes for automatic discovery by the registry.

## Contents

- `compressor_interface.py`: base contract for all compressor implementations.
- `*_compress.py`: concrete compressors backed by tools such as Ghostscript, FFmpeg, Pillow, and others.
- `__init__.py`: re-exports compressor classes so the registry can inspect the package and auto-register supported compressors.

## How To Work In This Folder

- Implement new compressors as subclasses of `CompressorInterface`.
- Define `supported_formats` on each compressor class. Input format equals output format; format-changing operations belong in `converters/`.
- Override `can_register()` when a compressor depends on a non-Python binary or optional runtime dependency.
- Lazy-import optional pip dependencies inside `compress()` so `compressors/__init__.py` stays importable in minimal environments.

## Practical Guidelines

- Make the compressor responsible for filesystem output creation under the provided output directory.
- Normalize formats using the interface's existing alias handling instead of duplicating extension mapping logic.
- Return a list of produced output paths from `compress()`, even when the compressor usually emits one file.
- Avoid importing the registry from compressor modules to prevent circular dependencies.
- If a compressor offers compression-level presets, populate `formats_with_compression_levels` with the formats those presets apply to.

## Typical Workflow

1. Create a new `*_compress.py` module with a `CompressorInterface` subclass.
2. Add the class to `__init__.py` so registry auto-discovery can see it.
3. Implement `can_compress()` and `compress()`.
4. Implement `can_register()` if external binaries or optional libraries are required.
5. Add tests for the new format mapping or compression behavior where feasible.
