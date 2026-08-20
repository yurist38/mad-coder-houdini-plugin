PYTHON ?= python3
RUFF_VERSION ?= 0.16.0
PLATFORM ?= macos-arm64
VERSION ?= 0.0.0-dev

.PHONY: check compile test lint typecheck install-ruff install-checks build-local

check: compile test lint typecheck

compile:
	$(PYTHON) -m compileall -q mad-coder/scripts/python scripts tests

test:
	$(PYTHON) -m unittest discover -s tests -v

lint:
	ruff check mad-coder/scripts/python scripts tests

typecheck:
	basedpyright

install-ruff:
	$(PYTHON) -m pip install "ruff==$(RUFF_VERSION)"

install-checks:
	$(PYTHON) -m pip install -r requirements-dev.txt

build-local:
	$(PYTHON) scripts/build_release.py --version "$(VERSION)" --platform "$(PLATFORM)"
