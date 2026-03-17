PYTHON ?= python3
VENV ?= .venv
PIP := $(VENV)/bin/pip
PRIVEX := $(VENV)/bin/privex

.PHONY: setup connect

setup:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install -r requirements.txt

connect:
	$(PRIVEX) connect
