# ============================================================================
# Transmute - Development Makefile
# ============================================================================
# Usage:
#   make help        Show available targets
#   make dev         Run backend + frontend in development mode
#   make build       Build the frontend for production
#   make lint        Run linters for backend and frontend
#   make clean       Remove build artifacts and temp data
#   make docker      Build and run via Docker Compose (dev)
# ============================================================================

# Use python3 explicitly; override with: make PYTHON=python
PYTHON ?= python3
VENV_DIR := .venv
VENV_PY := $(VENV_DIR)/bin/python3

.PHONY: help \
        dev dev-backend dev-frontend \
        install install-backend install-frontend \
        conv-count \
        build build-frontend \
        lint lint-frontend check \
        test test-backend test-frontend test-conversions test-compressions \
        docker docker-build docker-up docker-down docker-logs docker-prod \
        clean clean-build clean-data clean-venv clean-docker clean-all \
        venv

# Default target
help: ## Show this help message
	@echo ""
	@echo "Transmute Development Commands"
	@echo "=============================="
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ----------------------------------------------------------------------------
# Installation
# ----------------------------------------------------------------------------

install: install-backend install-frontend ## Install all dependencies

install-backend: venv ## Install Python backend dependencies
	$(VENV_PY) -m pip install -r requirements.txt

install-frontend: ## Install Node.js frontend dependencies
	cd frontend && npm ci 

# ----------------------------------------------------------------------------
# Development
# ----------------------------------------------------------------------------

dev: ## Run backend and frontend dev servers concurrently
	@echo "Starting backend and frontend..."
	@echo ""
	@trap 'kill 0' SIGINT SIGKILL EXIT; \
		$(MAKE) dev-backend & \
		$(MAKE) dev-frontend & \
		wait

dev-backend: venv ## Run the backend server
	$(VENV_PY) -m watchfiles "$(VENV_PY) backend/main.py" backend

dev-frontend: ## Run the Vite frontend dev server
	cd frontend && npm run dev

# ----------------------------------------------------------------------------
# Reporting
# ----------------------------------------------------------------------------
conv-count: venv ## Count total conversions in the database
	$(VENV_PY) backend/export_supported_conversions.py --report-only
# ----------------------------------------------------------------------------
# Build
# ----------------------------------------------------------------------------

build-frontend: ## Build the frontend for production
	cd frontend && npm run build

build: build-frontend ## Build all components (currently just frontend)

# ----------------------------------------------------------------------------
# Linting & Formatting
# ----------------------------------------------------------------------------

lint: lint-frontend ## Run all linters

lint-frontend: ## Lint frontend code with ESLint
	cd frontend && npm run lint


check: lint ## Run all checks (alias for lint)

# ----------------------------------------------------------------------------
# Testing
# ----------------------------------------------------------------------------

test: test-backend test-frontend

test-backend: venv ## Run Python backend tests with pytest
	$(VENV_PY) -m pytest backend \
		--ignore=backend/tests/converters/test_all_conversions.py \
		--ignore=backend/tests/compressors/test_all_compressions.py

test-frontend: ## Run frontend tests with Vitest. Still working on develop tests
	cd frontend && npm run test

# Skips pdf->cbz since the pdfs in samples/ will fail with PDF contains no extractable images: No valid images found in PDF file
# Can re-enable once we have a better test PDF
test-conversions: venv ## Run all conversion tests (currently skipped in CI)
	$(VENV_PY) -m pytest backend/tests/converters/test_all_conversions.py -k "not pdf->cbz"

test-compressions: venv ## Run all compression tests (currently skipped in CI)
	$(VENV_PY) -m pytest backend/tests/compressors/test_all_compressions.py

# ----------------------------------------------------------------------------
# Docker
# ----------------------------------------------------------------------------

docker: docker-build docker-up ## Build and start Docker dev container

docker-build: ## Build Docker image using dev compose
	docker compose -f docker-compose-dev.yml build

docker-up: ## Start Docker dev containers
# Note: docker backend runs as root, but frontend runs as user
	HOST_UID=$(shell id -u) HOST_GID=$(shell id -g) \
	docker compose -f docker-compose-dev.yml up -d

docker-down: ## Stop Docker dev containers
	docker compose -f docker-compose-dev.yml down

docker-logs: ## Tail Docker container logs
	docker compose -f docker-compose-dev.yml logs -f

docker-prod: ## Start production Docker containers (pulls image)
	docker compose up -d

# ----------------------------------------------------------------------------
# Cleanup
# ----------------------------------------------------------------------------

clean: clean-build ## Delete build artifacts

clean-build: ## Delete frontend build output and caches
	@echo ""
	@echo ""
	@echo "⚠️ This will delete frontend build output and caches."
	@echo ""
	@read -p "Are you sure? [y/n] " confirm && [ "$$confirm" = "y" ] || exit 1
	rm -rf frontend/dist
	rm -rf frontend/node_modules/.vite
	find backend -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find backend -type f -name "*.pyc" -delete 2>/dev/null || true

clean-data: ## Delete local data (uploads, outputs, tmp, db) ⚠️  destructive
	@echo ""
	@echo ""
	@echo "⚠️ This will delete all local data (uploads, outputs, db, tmp)."
	@echo ""
	@read -p "Are you sure? [y/n] " confirm && [ "$$confirm" = "y" ] || exit 1
	rm -rf data/uploads/* data/outputs/* data/tmp/* data/db/*

clean-venv: ## Delete python virtual environment
	@echo ""
	@echo ""
	@echo "⚠️ This will delete the python virtual environment."
	@echo ""
	@read -p "Are you sure? [y/n] " confirm && [ "$$confirm" = "y" ] || exit 1
	rm -rf $(VENV_DIR)

clean-docker: ## Stop docker container and delete docker dev volume
	@echo ""
	@echo ""
	@echo "⚠️ This will stop and delete the docker dev volume (uploads, outputs, db, tmp)."
	@echo ""
	@read -p "Are you sure? [y/n] " confirm && [ "$$confirm" = "y" ] || exit 1
	$(MAKE) docker-down
	docker volume rm transmute_backend_dev

clean-all: clean-build clean-data clean-venv clean-docker ## Remove everything (build artifacts + data + venv) ⚠️  destructive
	rm -rf frontend/node_modules

# ----------------------------------------------------------------------------
# Virtual Environment
# ----------------------------------------------------------------------------

$(VENV_DIR)/bin/activate:
	$(PYTHON) -m venv $(VENV_DIR)
	$(VENV_PY) -m pip install --upgrade pip

venv: $(VENV_DIR)/bin/activate ## Activate .venv (creates .venv first, if it doesn't exist yet)