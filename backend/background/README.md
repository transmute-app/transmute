# Background

This package contains background maintenance tasks that run outside the request-response path.

## Purpose

- House long-running or periodic jobs that should not live inside API route handlers.
- Perform operational cleanup work for uploaded files, converted files, and related metadata.
- Provide thread entrypoints that can be started by the application bootstrap code.

## Contents

- `cleanup.py`: periodic cleanup loop for uploaded and converted file records, including conversion relation cleanup.
- `__init__.py`: exports the background thread factory used by the app startup path.

## How To Work In This Folder

- Keep background jobs idempotent where possible. They may run repeatedly for the lifetime of the server.
- Use module loggers with `logging.getLogger(__name__)` instead of `print()` so logs follow the central uvicorn-style logging config.
- Avoid request-scoped assumptions. Background tasks should create or receive their own DB access objects.
- Keep scheduling concerns simple here. If a task needs configuration, read it from `SettingsDB` or `core.get_settings()`.

## Practical Guidelines

- Put task logic in small functions that can be tested independently from the infinite loop.
- Reserve thread creation for thin wrapper functions such as `get_upload_cleanup_thread()`.
- Be careful with file deletion and database mutations: always clean both disk state and metadata consistently.
- If a task grows beyond a small maintenance loop, split the reusable logic from the scheduler wrapper.

## Typical Workflow

1. Add or update a pure task function that performs one pass of work.
2. Wrap it in a loop or thread entrypoint only if the task must run continuously.
3. Log failures with the module logger.
4. Add tests around the task logic where practical.
