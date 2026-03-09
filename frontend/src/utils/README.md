# Utils

This folder contains shared frontend utility code.

## Purpose

- Centralize browser-facing helper logic used across pages and components.
- Keep API requests, auth token handling, error normalization, and download helpers consistent.

## Contents

- `api.ts`: fetch wrappers, auth token storage, auth-expiry signaling, and typed response helpers.
- `download.ts`: file download helpers used by feature pages.

## How To Work In This Folder

- Put generic helpers here only when they are used by more than one component or page, or when they enforce a frontend-wide convention.
- Extend `api.ts` when backend communication patterns need to stay consistent across the app.
- Keep helpers framework-light; they should support React code without depending on component state directly.

## Practical Guidelines

- Reuse `apiFetch`, `apiJson`, and related helpers instead of calling `fetch` directly in new code unless there is a specific reason not to.
- Keep auth token behavior centralized so session expiry stays consistent across the app.
- Normalize errors here when multiple screens need the same failure handling pattern.
- Avoid adding feature-specific business logic to utility modules.

## Typical Workflow

1. Add or update a reusable helper.
2. Replace duplicated page-level code with the shared helper.
3. Keep inputs and outputs explicit so the helper remains easy to test and reuse.
