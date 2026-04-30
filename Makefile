VENV   := .venv
PYTHON := $(VENV)/bin/python

install:
	python3.12 -m venv $(VENV)
	$(PYTHON) -m pip install -e .[dev]

test:
	$(PYTHON) -m pytest test/ -v

clean:
	rm -rf $(VENV) __pycache__ ng_parser/__pycache__ *.egg-info
