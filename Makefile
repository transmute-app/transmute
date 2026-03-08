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

.PHONY: help dev dev-backend dev-frontend build install install-backend \
        install-frontend lint lint-frontend clean clean-build \
        clean-data docker docker-build docker-up docker-down docker-logs \
        check

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

install-backend: ## Install Python backend dependencies
	$(PYTHON) -m pip install -r requirements.txt

install-frontend: ## Install Node.js frontend dependencies
	cd frontend && npm install

# ----------------------------------------------------------------------------
# Development
# ----------------------------------------------------------------------------

dev: ## Run backend and frontend dev servers concurrently
	@echo "Starting backend and frontend..."
	@echo "Backend: http://localhost:3313"
	@echo "Frontend: http://localhost:5173"
	@echo ""
	@trap 'kill 0' EXIT; \
		$(MAKE) dev-backend & \
		$(MAKE) dev-frontend & \
		wait

dev-backend: ## Run the backend server
	$(PYTHON) backend/main.py

dev-frontend: ## Run the Vite frontend dev server
	cd frontend && npm run dev

# ----------------------------------------------------------------------------
# Build
# ----------------------------------------------------------------------------

build: ## Build the frontend for production
	cd frontend && npm run build

# ----------------------------------------------------------------------------
# Linting & Formatting
# ----------------------------------------------------------------------------

lint: lint-frontend ## Run all linters

lint-frontend: ## Lint frontend code with ESLint
	cd frontend && npm run lint

check: lint ## Run all checks (alias for lint)

# ----------------------------------------------------------------------------
# Docker
# ----------------------------------------------------------------------------

docker: docker-build docker-up ## Build and start Docker dev environment

docker-build: ## Build Docker image using dev compose
	docker compose -f docker-compose-dev.yml build

docker-up: ## Start Docker dev containers
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

clean: clean-build ## Remove build artifacts

clean-build: ## Remove frontend build output and caches
	rm -rf frontend/dist
	rm -rf frontend/node_modules/.vite
	find backend -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find backend -type f -name "*.pyc" -delete 2>/dev/null || true

clean-data: ## Remove local data (uploads, outputs, tmp, db) ⚠️  destructive
	@echo "⚠️  This will delete all local data (uploads, outputs, db)."
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	rm -rf data/uploads/* data/outputs/* data/tmp/* data/db/*

clean-all: clean clean-data ## Remove everything (build artifacts + data) ⚠️  destructive
	rm -rf frontend/node_modules
