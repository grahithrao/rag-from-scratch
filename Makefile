# ==============================================================================
# RAG From Scratch — Developer Operations & Automation Makefile
# ==============================================================================

SHELL := /bin/bash
PYTHON ?= python3
VENV ?= .venv
BIN := $(VENV)/bin

.PHONY: help install install-dev run-backend run-frontend run test test-frontend test-cov lint format clean docker-build docker-up docker-down docker-logs sample-pdf

help: ## Show this help message
	@echo "Available commands:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Create virtual environment and install production dependencies
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -r requirements.txt
	@echo -e "\033[32mInstallation complete! Run 'source $(BIN)/activate'\033[0m"

install-dev: ## Install dev dependencies (pytest, ruff, mypy, httpx)
	$(BIN)/pip install pytest pytest-cov httpx ruff mypy types-requests

run-backend: ## Run FastAPI backend server (port 8001)
	$(BIN)/uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

run-frontend: ## Run Streamlit frontend application (port 8501)
	$(BIN)/streamlit run frontend/streamlit_app.py --server.port 8501

run: ## Start backend in background and frontend in foreground
	@echo "Starting FastAPI backend on :8001..."
	$(BIN)/uvicorn app.main:app --host 127.0.0.1 --port 8001 & echo $$! > .backend.pid
	@sleep 2
	@echo "Starting Streamlit UI on :8501..."
	$(BIN)/streamlit run frontend/streamlit_app.py

stop: ## Stop background backend server started via make run
	@if [ -f .backend.pid ]; then \
		kill -9 $$(cat .backend.pid) 2>/dev/null || true; \
		rm -f .backend.pid; \
		echo "Backend stopped."; \
	fi

test: ## Run complete pytest test suite
	$(BIN)/pytest -v

test-frontend: ## Run frontend smoke tests
	$(BIN)/pytest -v tests/test_frontend.py

test-cov: ## Run test suite with coverage report
	$(BIN)/pytest -v --cov=app --cov=frontend --cov-report=term-missing

lint: ## Lint codebase with ruff
	@which ruff >/dev/null 2>&1 && ruff check . || $(BIN)/ruff check .

format: ## Format codebase with ruff
	@which ruff >/dev/null 2>&1 && ruff format . || $(BIN)/ruff format .

sample-pdf: ## Generate sample document in project root
	$(BIN)/python scripts/make_sample_pdf.py

docker-build: ## Build Docker container image
	docker build -t rag-from-scratch:latest .

docker-up: ## Start backend and frontend services with docker-compose
	docker compose up -d --build
	@echo "Backend: http://localhost:8001/docs"
	@echo "Frontend: http://localhost:8501"

docker-down: ## Stop all docker-compose services
	docker compose down

docker-logs: ## Follow docker-compose logs
	docker compose logs -f

clean: ## Clean up caches, build artifacts, and temp files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	rm -rf .pytest_cache htmlcov .coverage
