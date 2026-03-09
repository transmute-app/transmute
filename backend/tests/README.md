# Tests

This package contains backend tests and test fixtures.

## Purpose

- Verify shared backend behavior, especially reusable helper logic and safety checks.
- Store fixture files used by backend tests.
- Keep test code separate from production modules while still following backend package boundaries.

## Contents

- `core/`: tests for shared helper and validation behavior.
- `fixtures/`: sample files used by media detection and related tests.
- `__init__.py`: package marker.

## Related Test Setup

- `backend/conftest.py` defines shared fixtures such as temporary directories and in-memory DB state.
- `backend/pytest.ini` sets `pythonpath = .` so backend modules can be imported directly during test runs.

## How To Work In This Folder

- Group tests by the backend package they exercise.
- Prefer small focused tests with explicit fixture setup.
- Put reusable pytest fixtures in `backend/conftest.py` instead of duplicating setup in each test module.
- Add files to `fixtures/` only when the behavior depends on actual file contents or extensions.

## Practical Guidelines

- Match test names to the behavior under test, not to implementation details.
- When a helper accepts both raise and no-raise modes, test both paths.
- Use temporary directories or in-memory database state for side-effect-heavy tests.
- Keep fixture files minimal but realistic enough to exercise format detection and path validation.

## Typical Workflow

1. Add or update a test module under the package area being changed.
2. Reuse fixtures from `backend/conftest.py` where possible.
3. Add fixture files to `fixtures/` only if synthetic in-memory inputs are not enough.
4. Run the affected backend tests before merging changes.
