.PHONY: help install install-dev run test lint lint-fix format format-check

help:
	@echo "Available targets:"
	@echo "  install        - pip install -r requirements.txt"
	@echo "  install-dev    - install runtime + dev deps"
	@echo "  run            - run the server"
	@echo "  test           - run unit tests"
	@echo "  lint           - run ruff check"
	@echo "  lint-fix       - run ruff with --fix"
	@echo "  format         - run black formatter"
	@echo "  format-check   - check formatting with black"

install:
	pip install -r requirements.txt

install-dev: install
	pip install -r requirements-dev.txt

run:
	python blog_server.py

test:
	python -m unittest discover -s tests -p 'test_*.py'

lint:
	ruff check .

lint-fix:
	ruff check --fix .

format:
	black .

format-check:
	black --check .

