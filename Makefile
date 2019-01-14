.PHONY: all build clean install manage migrate pep8 run setup-db shell test

# Project settings
LEVEL ?= development
PROJECT = betterbeauty
PYTHON = $(VIRTUAL_ENV)/bin/python3.6
PYTEST = $(VIRTUAL_ENV)/bin/pytest
VIRTUAL_ENV ?= venv

requirements = -r $(PROJECT)/requirements/$(LEVEL).txt

MYPYPATH=mypy
FLAKE8 = $(VIRTUAL_ENV)/bin/flake8
MYPY = $(VIRTUAL_ENV)/bin/mypy

DJANGO_SERVER ?= runserver
DJANGO_SHELL ?= shell_plus

SERVER_HOST ?= 0.0.0.0
SERVER_PORT ?= 8000

all: build

build: install-py migrate

manage:
	$(PYTHON) $(PROJECT)/manage.py $(COMMAND)

setup-db:
	. install_scripts/local_setup.sh

setup-db-osx:
	. install_scripts/local_osx_setup.sh

install-py: .install-py
.install-py: $(PROJECT)/requirements/common.txt $(PROJECT)/requirements/$(LEVEL).txt
	[ ! -d "$(VIRTUAL_ENV)/" ] && virtualenv -p python3.6 $(VIRTUAL_ENV)/ || :
	$(PYTHON) -m pip install --exists-action w $(requirements)

clean:
	@echo "cleaning compiled files..."
	@find . -name "*.pyc" -delete
	@find . -type d -empty -delete

migrate:
	COMMAND=migrate make manage

run: build
	COMMAND="$(DJANGO_SERVER) $(SERVER_HOST):$(SERVER_PORT)" $(MAKE) manage

shell: build
	COMMAND=shell_plus make manage

lint: flake8 mypy

mypy:
	MYPYPATH=$(MYPYPATH) $(MYPY) --ignore-missing-imports $(PROJECT)/

pytest:
	$(PYTEST) --ds=core.settings.tests --junit-xml=test-reports/junit/testresults.xml \
		--cov=$(PROJECT) --cov-report term --cov-report xml \
		--cov-report html:test-reports/coverage-html $(TEST_ARGS) $(PROJECT)

test: clean lint pytest
	LEVEL=tests

fasttest: clean pytest

e2e-test:
	$(PYTHON) tests/e2e.py

flake8:
	$(FLAKE8) --statistics ./$(PROJECT)/
