# Registry

This package discovers and serves the set of available converter, downloader, and compressor implementations.

## Purpose

- Auto-register converter classes exported by the `converters` package.
- Auto-register downloader classes exported by the `downloaders` package.
- Auto-register compressor classes exported by the `compressors` package.
- Answer questions about supported formats and valid conversion paths.
- Provide single shared registry instances used by the rest of the backend.

## Contents

- `registry.py`: `ConverterRegistry` implementation and the shared `registry` instance.
- `downloader_registry.py`: `DownloaderRegistry` implementation and the shared `downloader_registry` instance.
- `compressor_registry.py`: `CompressorRegistry` implementation and the shared `compressor_registry` instance.
- `__init__.py`: package exports for the registry types and singletons.

## How To Work In This Folder

- Keep discovery and format lookup logic here, not in route handlers.
- Treat the shared `registry`, `downloader_registry`, and `compressor_registry` instances as the default application entrypoints for capability lookups.
- Only extend a registry API when its consumers need a new query pattern.
- Let converters, downloaders, and compressors describe themselves through class attributes and methods instead of hard-coding format maps here.

## Practical Guidelines

- If a new converter, downloader, or compressor is exported from its package's `__init__`, the corresponding registry should usually discover it automatically.
- Use `can_register()` on classes to skip integrations that are unavailable in the current runtime.
- Keep normalization behavior consistent with `core.media_type_aliases`.
- Avoid storing request-specific or user-specific state in any registry.
- Compressor lookup is keyed by a single media type (input == output); format-changing operations remain owned by converters.

## Typical Workflow

1. Add or update a converter, downloader, or compressor in its package.
2. Verify it is exported from that package's `__init__`.
3. Use or extend the registry methods only if new lookup behavior is required.
4. Keep the shared registry instances importable and side-effect safe.
