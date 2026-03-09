# Core

This package contains backend-wide utilities, configuration, and shared application services.

## Purpose

- Centralize settings, logging, auth helpers, media type aliases, and reusable helper functions.
- Keep cross-cutting concerns out of route handlers, converters, and database classes.
- Provide stable imports for the rest of the backend through `core.__init__`.

## Contents

- `settings.py`: application configuration and derived runtime paths.
- `logging.py`: central logging setup based on uvicorn's default log configuration.
- `auth.py`: token and password-related auth helpers.
- `media_types.py`: alias mapping and normalization support for media types.
- `helper_functions.py`: shared filesystem, validation, hashing, and cleanup helpers.
- `__init__.py`: curated exports for commonly used core utilities.

## How To Work In This Folder

- Put shared logic here only if it is genuinely used across multiple backend areas.
- Keep this package dependency-light. Avoid importing route modules or registry code into `core`.
- Use `settings.py` for runtime configuration and derived paths rather than hard-coding directories elsewhere.

## Practical Guidelines

- If a helper needs request-specific behavior or HTTP exceptions, check whether it truly belongs here or in the API layer.
- Keep exported helpers in `__init__.py` intentional. Re-export only the pieces meant for broad use.
- Favor pure utility functions where possible, especially for validation and normalization code.
- Be cautious with changes here: this package is imported broadly across the backend.

## Typical Workflow

1. Add or update a shared utility, config object, or helper module.
2. Re-export it from `__init__.py` only if it should be used widely.
3. Update tests that cover the helper behavior.
4. Keep new code generic enough to be reused by routes, DB classes, or background tasks.
