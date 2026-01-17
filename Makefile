.PHONY: help install install-dev run run-network lint format typecheck clean

help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## Install production dependencies
	pip install -r requirements.txt

install-dev:  ## Install development dependencies
	pip install -e ".[dev]"

run:  ## Run the Streamlit app locally
	streamlit run sail_plan_app.py

run-network:  ## Run the app accessible on the network
	streamlit run sail_plan_app.py --server.address 0.0.0.0

lint:  ## Run linting with ruff
	ruff check sail_plan_app.py

format:  ## Format code with ruff
	ruff format sail_plan_app.py
	ruff check --fix sail_plan_app.py

typecheck:  ## Run type checking with mypy
	mypy sail_plan_app.py

clean:  ## Remove build artifacts and cache files
	rm -rf __pycache__ .mypy_cache .ruff_cache *.egg-info dist build
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
