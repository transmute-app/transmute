# API

This package defines the FastAPI HTTP surface for the backend.

## Purpose

- Assemble the application's routers into a single API entrypoint.
- Define request and response schemas used by route handlers.
- Provide FastAPI dependency functions for authentication and shared database access.
- Keep HTTP concerns separate from lower-level business logic in `core`, `db`, `registry`, and `converters`.

## Contents

- `__init__.py`: builds the top-level `APIRouter` and registers route modules.
- `deps.py`: shared FastAPI dependencies for auth, current user resolution, and singleton-style DB access.
- `schemas.py`: Pydantic models used by the API layer.
- `routes/`: endpoint modules grouped by resource or feature area.

## How To Work In This Folder

- Add new endpoints as a route module under `routes/` when the feature exposes HTTP behavior.
- Put shared auth, user, or database dependency wiring in `deps.py` instead of duplicating it in handlers.
- Keep route handlers thin: validate inputs, call lower-level helpers, and map failures to HTTP responses.
- Prefer response models in `schemas.py` for anything reused or non-trivial.
- Reuse existing tags and route prefixes unless the new feature is a clearly separate resource.

## Practical Guidelines

- If a change is about file system safety, metadata cleanup, or shared utilities, it probably belongs in `core` rather than here.
- If a change is about SQLite persistence, add it to the relevant class in `db` and consume it through `deps.py`.
- If a change adds a new conversion capability, implement the converter in `converters`, let `registry` discover it, and only expose the new behavior through routes if the HTTP contract changes.
- Keep exceptions explicit. Route code should raise `HTTPException` for user-facing failures rather than leaking raw Python errors.

## Typical Workflow

1. Define or update a schema in `schemas.py` if the request or response shape changes.
2. Add or modify the route handler in `routes/`.
3. Reuse dependencies from `deps.py` for DB instances and authenticated users.
