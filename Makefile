.PHONY: help build run test lint clean docker-build docker-run

# Default target
help:
	@echo "QA Data Pipeline - Available commands:"
	@echo ""
	@echo "  make install     - Install dependencies"
	@echo "  make test        - Run tests"
	@echo "  make lint        - Run linter"
	@echo "  make format      - Format code with black"
	@echo "  make clean       - Clean build artifacts"
	@echo ""
	@echo "  make docker-build - Build Docker image"
	@echo "  make docker-run   - Run with Docker"
	@echo "  make monitoring   - Start monitoring stack"
	@echo ""
	@echo "  make flag INPUT=<file>     - Generate flags"
	@echo "  make autofill INPUT=<file> - Auto-fill from AI"
	@echo ""

# Development
install:
	pip install -r requirements.txt

test:
	pytest tests/ -v --cov=src --cov-report=term-missing

lint:
	flake8 src/ tests/ --max-line-length=100
	mypy src/

format:
	black src/ tests/ main.py

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +

# Docker
docker-build:
	docker build -t qa-data-pipeline:latest .

docker-run:
	docker-compose up qa-pipeline

monitoring:
	docker-compose --profile monitoring up -d

monitoring-down:
	docker-compose --profile monitoring down

# Pipeline commands
flag:
	python main.py flag $(INPUT) -o data/output/flagged.xlsx

autofill:
	python main.py autofill $(INPUT) -o data/output/autofilled.xlsx

merge:
	python main.py merge $(ORIGINAL) $(FLAGGED) -o data/output/merged.xlsx
