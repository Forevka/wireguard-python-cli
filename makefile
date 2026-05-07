VENV    := .venv
PYTHON  := $(VENV)/bin/python
PIP     := $(VENV)/bin/pip

.DEFAULT_GOAL := help

.PHONY: help install run clean

help:
	@echo ""
	@echo "  make install   Create venv and install dependencies"
	@echo "  make run       Run wg_manager.py (pass ARGS='...' for subcommands)"
	@echo "  make clean     Remove the virtual environment"
	@echo ""
	@echo "  Examples:"
	@echo "    make run ARGS='list'"
	@echo "    make run ARGS='add phone'"
	@echo "    make run ARGS='qr laptop'"
	@echo ""

install:
	@echo "→ Creating virtual environment..."
	python3 -m venv $(VENV)
	@echo "→ Installing dependencies..."
	$(PIP) install --quiet --upgrade pip
	$(PIP) install --quiet -r requirements.txt
	@echo ""
	@echo "✓ Done. Run the tool with:"
	@echo "    sudo $(PYTHON) wg_manager.py <command>"
	@echo "  or:"
	@echo "    make run ARGS='<command>'"
	@echo ""

run:
	sudo $(PYTHON) wg_manager.py $(ARGS)

clean:
	rm -rf $(VENV)
	@echo "✓ Virtual environment removed."