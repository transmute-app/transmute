# Registry

This package discovers and serves the set of available converter implementations.

## Purpose

- Auto-register converter classes exported by the `converters` package.
- Answer questions about supported formats and valid conversion paths.
- Provide a single shared registry instance used by the rest of the backend.

## Contents

- `registry.py`: `ConverterRegistry` implementation and the shared `registry` instance.
- `__init__.py`: package exports for the registry types and singleton.

## How To Work In This Folder

- Keep discovery and format lookup logic here, not in route handlers.
- Treat the shared `registry` instance as the default application entrypoint for conversion capability lookups.
- Only extend the registry API when converter consumers need a new query pattern.
- Let converters describe themselves through class attributes and methods instead of hard-coding format maps here.

## Practical Guidelines

- If a new converter is exported from `converters.__init__`, the registry should usually discover it automatically.
- Use `can_register()` on converters to skip integrations that are unavailable in the current runtime.
- Keep normalization behavior consistent with `core.media_type_aliases`.
- Avoid storing request-specific or user-specific state in the registry.

## Typical Workflow

1. Add or update a converter in `converters`.
2. Verify it is exported from `converters.__init__`.
3. Use or extend `ConverterRegistry` methods only if new lookup behavior is required.
4. Keep the shared `registry` instance importable and side-effect safe.
