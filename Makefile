.PHONY: clean install test lint format

clean:
	find . -type d -name "__pycache__" -exec rm -r {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -r {} +
	find . -type d -name "*.egg" -exec rm -r {} +
	find . -type d -name ".pytest_cache" -exec rm -r {} +
	find . -type d -name "build" -exec rm -r {} +
	find . -type d -name "dist" -exec rm -r {} +
	rm -rf output/ crawled_data/ ecommerce_data/ screenshots/

install:
	pip install -e ".[dev]"
	playwright install

test:
	python -m pytest tests/ -v

lint:
	black src/ tests/
	isort src/ tests/
	flake8 src/ tests/

format:
	black src/ tests/
	isort src/ tests/ 