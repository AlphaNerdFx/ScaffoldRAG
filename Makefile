# =============================================================================
# ScaffoldRAG: Engineering Automation Makefile
# Target Standard: POSIX | Self-Documenting | Virtualenv Enforced
# =============================================================================

.DEFAULT_GOAL := help
SHELL := /bin/bash

# Configuration Variables
PYTHON := python3
POETRY := $(PYTHON) -m poetry
QDRANT_HOST ?= localhost
QDRANT_HTTP_PORT ?= 6333
QDRANT_GRPC_PORT ?= 6334
QDRANT_COLLECTION ?= engineering_blueprints
GROQ_API_KEY ?= gsk_development_dummy_key_0000000000000000000000

# -----------------------------------------------------------------------------
# Help Target (Self-Documenting)
# -----------------------------------------------------------------------------
.PHONY: help
help: ## Display this automated help menu
	@echo "============================================================================="
	@echo "ScaffoldRAG: Engineering Task Automation"
	@echo "============================================================================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'

# -----------------------------------------------------------------------------
# Environment & Dependency Management
# -----------------------------------------------------------------------------
.PHONY: install
install: ## Install production and development dependencies via Poetry
	$(POETRY) install --no-interaction
	pip install -e .

.PHONY: install-frontend
install-frontend: ## Install optional Streamlit frontend dependencies
	$(POETRY) install --with frontend --no-interaction

.PHONY: lock
lock: ## Update and synchronize poetry.lock with pyproject.toml
	$(POETRY) lock

# -----------------------------------------------------------------------------
# Static Quality Gates (CI Gate 1 & 2)
# -----------------------------------------------------------------------------
.PHONY: lint
lint: ## Run Ruff linter checks
	$(POETRY) run ruff check .

.PHONY: lint-fix
lint-fix: ## Automatically fix linting violations and organize imports
	$(POETRY) run ruff check --select I --fix .
	$(POETRY) run ruff check --fix .

.PHONY: format-check
format-check: ## Verify code formatting compliance without modifying files
	$(POETRY) run ruff format --check .

.PHONY: format
format: ## Format all Python code to enforce the 100-character line limit and LF endings
	$(POETRY) run ruff format .

.PHONY: typecheck
typecheck: ## Execute Mypy static type checking across the application
	$(POETRY) run mypy --show-error-context --show-column-numbers --pretty app/

# -----------------------------------------------------------------------------
# Data Ingestion & Blueprints (CI Gate 3)
# -----------------------------------------------------------------------------
.PHONY: lint-blueprints
lint-blueprints: ## Run static AST and tradeoff rubric validation on markdown blueprints
	$(POETRY) run python scripts/lint_blueprints.py

.PHONY: ingest
ingest: ## Ingest all 15 markdown blueprints into Qdrant vector store
	QDRANT_HOST=$(QDRANT_HOST) \
	QDRANT_HTTP_PORT=$(QDRANT_HTTP_PORT) \
	QDRANT_GRPC_PORT=$(QDRANT_GRPC_PORT) \
	QDRANT_COLLECTION_NAME=$(QDRANT_COLLECTION) \
	GROQ_API_KEY=$(GROQ_API_KEY) \
	$(POETRY) run python scripts/ingest_corpus.py

.PHONY: generate-golden-dataset
generate-golden-dataset: ## Regenerate tests/golden_dataset.json from blueprint ASTs
	$(POETRY) run python scripts/generate_golden_dataset.py

# -----------------------------------------------------------------------------
# Automated Testing & Benchmarks (CI Gate 4 & 5)
# -----------------------------------------------------------------------------
.PHONY: test
test: ## Run unit and integration tests
	$(POETRY) run pytest tests/ -v

.PHONY: test-cov
test-cov: ## Run unit tests with line coverage assertions (>= 85% requirement)
	QDRANT_HOST=$(QDRANT_HOST) \
	QDRANT_HTTP_PORT=$(QDRANT_HTTP_PORT) \
	QDRANT_GRPC_PORT=$(QDRANT_GRPC_PORT) \
	QDRANT_COLLECTION_NAME=$(QDRANT_COLLECTION) \
	GROQ_API_KEY=$(GROQ_API_KEY) \
	$(POETRY) run pytest --cov=app --cov-report=term-missing --cov-fail-under=85 -vv -rA tests/

.PHONY: benchmark
benchmark: ## Execute Context Precision@4 retrieval benchmark against golden dataset
	QDRANT_HOST=$(QDRANT_HOST) \
	QDRANT_HTTP_PORT=$(QDRANT_HTTP_PORT) \
	QDRANT_GRPC_PORT=$(QDRANT_GRPC_PORT) \
	QDRANT_COLLECTION_NAME=$(QDRANT_COLLECTION) \
	$(POETRY) run pytest tests/benchmarks/test_retrieval_precision.py -vv -s

.PHONY: ci-local
ci-local: lint format-check typecheck test-cov benchmark ## Run the full 5-gate CI pipeline locally
	@echo "============================================================================="
	@echo "SUCCESS: All 5 CI quality gates passed locally!"
	@echo "============================================================================="

# -----------------------------------------------------------------------------
# Containerization & Orchestration
# -----------------------------------------------------------------------------
.PHONY: docker-build
docker-build: ## Build production multi-stage Docker image and measure footprint
	time docker build -t scaffold-rag:latest .
	docker images scaffold-rag:latest --format "Repository: {{.Repository}} | Tag: {{.Tag}} | Size: {{.Size}}"

.PHONY: docker-up
docker-up: ## Start Qdrant and FastAPI services via Docker Compose
	docker compose up -d

.PHONY: docker-down
docker-down: ## Stop all containerized services and preserve volumes
	docker compose down

.PHONY: docker-clean
docker-clean: ## Stop services and delete named volumes (wipes database)
	docker compose down -v

# -----------------------------------------------------------------------------
# Cleanup
# -----------------------------------------------------------------------------
.PHONY: clean
clean: ## Remove compiler caches, test artifacts, and build directories
	rm -rf .pytest_cache .ruff_cache .mypy_cache dist .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true