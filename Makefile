.PHONY: help
.DEFAULT_GOAL := help

define PRINT_HELP_PYSCRIPT
import re, sys

for line in sys.stdin:
	match = re.match(r'^([a-zA-Z_-]+):.*?## (.*)$$', line)
	if match:
		target, help = match.groups()
		print("%-20s %s" % (target, help))
endef
export PRINT_HELP_PYSCRIPT

help:
	@python -c "$$PRINT_HELP_PYSCRIPT" < $(MAKEFILE_LIST)

install: ## install dependencies
	poetry install

orthographic: orthographic-light orthographic-dark  ## Generates the orthographic maps

orthographic-light: ## Generates the orthographic map in light-mode
	poetry run python new_caledonia_maps/orthographic.py --light

orthographic-dark: ## Generates the orthographic map in dark-mode
	poetry run python ncn_milepost_openstreetmap_map/main.py --dark

lint: ## Checks for linting errors
	poetry run flake8

update-engraver: ## upgrades map-engraver to latest version of master
	poetry remove map-engraver || true
	poetry add git+https://github.com/leifgehrmann/map-engraver.git
	poetry install
