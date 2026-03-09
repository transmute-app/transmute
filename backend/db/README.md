# DB

This package contains the SQLite access layer for backend persistence.

## Purpose

- Encapsulate SQL table creation and metadata queries behind small Python classes.
- Separate persistence concerns from API handlers and converter logic.
- Provide one class per logical table or storage concern.

## Contents

- `file_db.py`: metadata storage for uploaded files.
- `conversion_db.py`: metadata storage for converted outputs.
- `conversion_relations_db.py`: relationships between source and converted files.
- `settings_db.py`: persisted application settings.
- `default_formats_db.py`: user or app defaults for preferred formats.
- `user_db.py`: users and roles.
- `api_key_db.py`: API key storage and lookup.
- `__init__.py`: package exports for the DB layer.

## How To Work In This Folder

- Keep SQL statements inside the relevant DB class instead of scattering queries across the codebase.
- Validate identifiers before interpolating table names. This package already relies on validated names and parameterized values.
- Add schema migration support where needed rather than assuming a clean database.
- Keep the public methods small and task-oriented so they are easy to reuse from dependencies and services.

## Practical Guidelines

- Use parameterized queries for values.
- When adding a column, update table creation and migration behavior together.
- Preserve thread-safety expectations. Existing classes use thread-local SQLite connections.
- Keep return types predictable: dictionaries for row data, `None` for missing records, and explicit method names for side effects.

## Typical Workflow

1. Add or update a method on the relevant DB class.
2. Update schema creation and migration logic if the stored shape changes.
3. Expose the class through `__init__.py` if it is new.
4. Reuse the class through API dependencies or background task code rather than opening raw SQLite connections elsewhere.
