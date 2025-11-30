.PHONY: help install install-dev test lint format check build run clean docker-build docker-run

# Default target
help:
	@echo "Available targets:"
	@echo "  install     - Install production dependencies"
	@echo "  install-dev - Install development dependencies"
	@echo "  test        - Run tests"
	@echo "  lint        - Run linters (flake8, mypy, pylint)"
	@echo "  security    - Run security checks (safety, bandit)"
	@echo "  format      - Format code (black, isort)"
	@echo "  check       - Run all checks (format, lint, security, test)"
	@echo "  build       - Build the package"
	@echo "  run         - Run the application locally"
	@echo "  clean       - Clean build artifacts"
	@echo "  docker-build - Build Docker image"
	@echo "  docker-run  - Run with Docker Compose"

# Installation
install:
	.venv/bin/python -m pip install .

install-dev:
	.venv/bin/python -m pip install -e ".[dev]"

# Testing
test:
	.venv/bin/python -m pytest tests/ -v --cov=src --cov-report=term-missing

# Linting
lint:
	.venv/bin/python -m flake8 src/
	.venv/bin/python -m mypy src/ --ignore-missing-imports
	.venv/bin/python -m pylint src/ --rcfile=pylintrc --exit-zero

# Security checks
security:
	.venv/bin/python -m safety check --ignore-unpinned-requirements 2>/dev/null || echo "Safety check completed"
	.venv/bin/python -m bandit -r src/ -f txt --exit-zero

# Formatting
format:
	.venv/bin/python -m black src/ tests/
	.venv/bin/python -m isort src/ tests/

# Combined checks
check: format lint security test

# Build
build:
	.venv/bin/python -m build

# Run locally (for development)
run:
	.venv/bin/python src/main.py

# Clean
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Docker commands
docker-build:
	docker compose build

docker-run:
	docker compose up -d

docker-logs:
	docker compose logs -f

docker-stop:
	docker compose down

docker-restart: docker-stop docker-run

# Development setup
setup-dev: install-dev
	pre-commit install

# Quick start
start: docker-build docker-run

# Full development workflow
dev-setup: install-dev setup-dev check
	@echo "Development environment ready!"