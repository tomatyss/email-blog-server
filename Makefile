.PHONY: help install install-dev run test lint lint-fix format format-check

VENV ?= .venv
PYTHON ?= $(VENV)/bin/python
PIP ?= $(PYTHON) -m pip
RUFF ?= $(VENV)/bin/ruff
BLACK ?= $(VENV)/bin/black

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

$(PYTHON):
	python3 -m venv $(VENV)

install: $(PYTHON)
	$(PIP) install -r requirements.txt

install-dev: install
	$(PIP) install -r requirements-dev.txt

run:
	$(PYTHON) blog_server.py

test:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py'

lint:
	$(RUFF) check .

lint-fix:
	$(RUFF) check --fix .

format:
	$(BLACK) .

format-check:
	$(BLACK) --check .
