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
	python3 -m pip install .

install-dev:
	python3 -m pip install -e ".[dev]"

# Testing
test:
	python3 -m pytest tests/ -v --cov=src --cov-report=term-missing

# Linting
lint:
	python3 -m flake8 src/
	python3 -m mypy src/ --ignore-missing-imports
	python3 -m pylint src/ --rcfile=pylintrc --exit-zero

# Security checks
security:
	python3 -m safety check
	python3 -m bandit -r src/ -f txt

# Formatting
format:
	python3 -m black src/ tests/
	python3 -m isort src/ tests/

# Combined checks
check: format lint security test

# Build
build:
	python3 -m build

# Run locally (for development)
run:
	python3 src/main.py

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