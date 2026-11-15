# Contributing

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.129-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6?logo=typescript&logoColor=white)

First off, thank you for your interest in contributing ❤️

This project is intended to be a reliable, self-hosted tool, and contributions of all kinds are welcome: code, documentation, bug reports, ideas, and feedback.

Want to instead contribute to our [website](https://transmute.sh)? Check out [transmute-app/transmute-app.github.io](https://github.com/transmute-app/transmute-app.github.io).

> [!CAUTION]
>
> ## No Autonomous Agents or Unreviewed AI Contributions
>
> This repository does not accept contributions submitted by autonomous agents or AI systems without direct human authorship, review, and accountability.
>
> All pull requests must come from a human contributor who understands, validates, and takes responsibility for the proposed changes.
>
> AI-assisted development is allowed, but blindly accepted or fully agent-generated contributions are not. If you use AI tooling, you are expected to verify correctness, understand the implementation, and stand behind the final submission.
>
> Maintainers may reject contributions without review if they appear to be primarily autonomous, low-effort AI output, or otherwise lack clear human ownership. (25k line PRs, etc.)

---

## Ways to Contribute

You can help by:

* Reporting bugs
* Suggesting features or improvements
* Improving documentation
* Adding new converters
* Fixing issues
* Reviewing pull requests

If you are unsure where to start, check the open issues or look for issues labeled `good first issue`.

---

## Getting Started

### 1. Fork and Clone

1. Click **Fork** at the top-right of the [transmute repository](https://github.com/transmute-app/transmute) to create your own copy.
2. Clone your fork locally:

```bash
git clone https://github.com/<your-username>/transmute.git
cd transmute
```

3. Add the upstream remote so you can keep your fork in sync:

```bash
git remote add upstream https://github.com/transmute-app/transmute.git
```

### 2. Create a Branch

```bash
git checkout -b feature/my-feature
```

Use descriptive branch names.

Examples:

* `feature/csv-to-png`
* `fix/job-progress`
* `docs/api-clarification`

### 3. Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/) for all commit messages:

| Prefix    | Use for                          |
| --------- | -------------------------------- |
| `feat:`   | New features                     |
| `fix:`    | Bug fixes                        |
| `docs:`   | Documentation changes            |
| `style:`  | Formatting, whitespace, etc.     |
| `refactor:` | Code changes that aren't fixes or features |
| `test:`   | Adding or updating tests         |
| `chore:`  | Build tasks, CI, dependencies    |

Examples:

* `feat: add TIFF to WebP conversion`
* `fix: handle empty file extension on upload`
* `docs: update API examples in README`

### 4. Build and Run the dev environment

### Docker Container (Recommended)

> [!NOTE]
> 
> Hot-reload is enabled, so any changes to files under backend/ or frontend/ trigger a reload of those files, so you can see the effects of your changes almost immediately, without restarting the docker container.
> 
> Saving changes to any file under backend/ will log you out, and it will take a few seconds for the reload to complete and allow you to log back in.
>
> Saving changes to any file under frontend/ will apply changes that will be immediately visible in your browser.

```bash
# Build and run the dev docker container
make docker

# To stop the container, use
make docker-down
```

### Alternatively, the dev environment can be built and run directly.


> [!WARNING]
> 
> The docker method above does not share the same data as this alternative method. So db, uploads, cache, accounts, etc are independent from one method to the other.
> 
> This method stores its data under data/ in the root folder of the app

> [!NOTE]
> 
> Hot-reload is enabled here too, for both backend/ and frontend/ files.


```bash
# Install dependencies
make install

# Launch dev server backend and frontend
make dev

# To close the app, CTRL+C in the terminal where `make dev` was run.
```

The app frontend runs on http://localhost:5173 (same for both docker and direct method). 
If you get `ERR_EMPTY_RESPONSE`, wait a bit and refresh. The backend needs time to load.

Feel free to reach out via issue if you hit any snags.

---

## Make Commands

A `Makefile` is included to simplify common development tasks. Run `make help` to see all available targets.

### Quick Reference

| Command | Description |
| --- | --- |
| `make help` | Show all available commands |
| `make install` | Install all dependencies (backend + frontend) |
| `make dev` | Run backend and frontend dev servers concurrently |
| `make build` | Build the frontend for production |
| `make lint` | Run all linters (currently frontend ESLint) |
| `make test` | Run backend and frontend tests |
| `make conv-count` | Report the total number of supported conversions |
| `make clean` | Remove build artifacts and caches |
| `make docker` | Build and start the Docker dev environment |

### Installation

```bash
# Install dependencies for backend and frontend
make install

# Or install individually
make install-backend    # creates .venv/ if needed, then pip installs requirements.txt
make install-frontend   # npm ci in frontend/

# Create the virtual environment without installing anything
make venv
```

### Development

```bash
# Start both backend (localhost:3313) and frontend (localhost:5173)
make dev

# Or run them individually
make dev-backend    # runs backend/main.py under watchfiles (auto-restarts on changes)
make dev-frontend   # runs the Vite dev server
```

### Reporting

```bash
# Count total conversions in the database
make conv-count
```

### Building

```bash
# Build frontend for production
make build

# Equivalent, since the frontend is currently the only component
make build-frontend
```

### Linting

```bash
# Run all linters
make lint

# Run just frontend ESLint
make lint-frontend

# Alias for `make lint`
make check
```

### Testing

```bash
# Run backend and frontend tests
make test

# Or run them individually
make test-backend    # pytest on backend/, excluding the slow all-conversions/all-compressions suites
make test-frontend   # Vitest (frontend tests are still being developed)

# Slow, exhaustive suites (currently skipped in CI)
make test-conversions   # all conversions, except pdf->cbz (sample PDFs contain no extractable images)
make test-compressions  # all compressions
```

### Docker

```bash
# Build image and start containers (dev)
make docker

# Or run steps individually
make docker-build   # Build the image using docker-compose-dev.yml
make docker-up      # Start containers
make docker-down    # Stop containers
make docker-logs    # Tail container logs

# Start production containers (pulls from registry)
make docker-prod
```

### Cleanup

The `clean-*` targets are destructive and prompt for confirmation before deleting anything.

```bash
# Remove build artifacts (frontend/dist, Vite cache, __pycache__, *.pyc)
make clean          # alias for make clean-build

# Remove local data (data/uploads, data/outputs, data/tmp, data/db)
make clean-data

# Remove the Python virtual environment
make clean-venv

# Stop the Docker dev container and delete its volume
make clean-docker

# Remove everything (build artifacts, local data, .venv, Docker volume, and frontend/node_modules)
make clean-all
```

> [!Note]
> 
> The `PYTHON` variable controls which binary is used to *create* `.venv/` (it defaults to `python3`). If your system uses a different binary, override it once when installing: `make PYTHON=python install`.


---

## Project Architecture (High Level)

Core components:

* **API** — FastAPI application
* **Workers** — background job processing (Not yet implemented)
* **Converters** — plugin-style conversion modules
* **Storage** — filesystem for files, SQLite for metadata
* **Queue** — Redis (Not yet implemented)

Converters follow a shared base class and are registered via the converter registry.

---

## Adding a New Converter

Contributions adding new converters are very welcome.

General expectations:

* Extend the base `ConverterInterface` class
* Declare supported inputs and outputs
* Implement the `convert()` method
* Include basic validation and error handling

Please keep converters:

* Deterministic
* Side-effect limited
* Safe for untrusted input files

If external binaries are required (e.g., ffmpeg, pandoc), document them clearly.

---

## Code Style

We aim for clean, readable code.

General guidelines:

* Prefer clarity over cleverness
* Keep functions focused and small
* Add docstrings where helpful
* Use type hints when possible
* Follow existing patterns in the codebase

Formatting and linting tools may be added or enforced over time.

---

## Pull Request Process

1. Ensure your branch is up to date with `main`
2. Make focused changes (avoid unrelated modifications)
3. Add or update tests if applicable
4. Update documentation if behavior changes
5. Open a Pull Request with a clear description

PRs should explain:

* What changed
* Why it changed
* How it was tested

Small PRs are preferred over large ones.

---

## Reporting Bugs

Please use the bug report template and include:

* Steps to reproduce
* Expected behavior
* Actual behavior
* Logs or screenshots (if available)
* Environment details

---

## Feature Requests

Feature requests are welcome. Please describe:

* The problem you want solved
* Proposed solution (if any)
* Alternatives considered

---

## Security

If you discover a security vulnerability, **do not open a public issue**.

Instead, please contact the maintainers privately (see [SECURITY](https://github.com/transmute-app/transmute/security/policy)).

---

## Philosophy

This project prioritizes:

* Simplicity
* Reliability
* Self-host friendliness
* Transparency
* Extensibility

We try to avoid unnecessary complexity and heavy dependencies unless they provide clear value.

---

## Questions

If you have questions, feel free to ask it using the "Question" issue template.

---

## License

By contributing, you agree that your contributions will be licensed under the same license as this project.
