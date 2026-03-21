PYTHON ?= python3
VENV ?= .venv
PIP := $(VENV)/bin/pip
PRIVEX := $(VENV)/bin/privex

.PHONY: setup init connect

setup:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install -r requirements-dev.txt

init:
	$(PRIVEX) init --connect

connect:
	$(PRIVEX) connect
