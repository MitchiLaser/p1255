
SHELL := /bin/bash

.SILENT: build clean devenv docs publish test lint
.IGNORE: clean
.ONESHELL:

BLUE:=\033[0;34m
RED:=\033[0;31m
NC:=\033[0m # No Color
BOLD:=$(tput bold)
NORM:=$(tput sgr0)

# the location of this file.
DIR:=$(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))

# build the package from the source
build: devenv
	. venv/bin/activate;
		python -m build;
		twine check --strict dist/*

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf src/p1255.egg-info/
	rm -rf venv/
	rm -rf `find . -type d -name __pycache__`

devenv:
	if [ ! -d "$(DIR)/venv" ]; then
		echo "Creating venv";
		python -m venv venv/;
	fi
	@if ! venv/bin/python -c "import p1255" 2>/dev/null; then
		echo "Installing p1255 in editable mode";
		. venv/bin/activate;
		pip install --upgrade -e .;
		pip install --upgrade twine build flake8 black isort;
	fi

publish: build
	echo "uploading build to PyPI"
	. venv/bin/activate;
		twine upload ./dist/*

lint: devenv
	. venv/bin/activate;
		echo -e "$(BLUE)${BOLD}ISORT${NC}$(NORM)";
		isort --check --diff ./src/p1255;
		RET_Isort=$$?;
		echo -e "$(BLUE)${BOLD}BLACK${NC}$(NORM)";
		black --check --color --diff ./src/p1255;
		RET_Black=$$?;
		echo -e "$(BLUE)${BOLD}FLAKE8${NC}$(NORM)";
		flake8 --config .flake8 ./src/p1255;
		RET_Flake8=$$?;
		if [ $$RET_Isort -ne 0 ] || [ $$RET_Black -ne 0 ] || [ $$RET_Flake8 -ne 0 ]; then
			echo -e "$(RED)${BOLD}Linting failed${NC}$(NORM)";
			exit 1;
		fi
