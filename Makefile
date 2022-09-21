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
	@python3 -c "$$PRINT_HELP_PYSCRIPT" < $(MAKEFILE_LIST)

install: ## install dependencies
	poetry install

download_ne_data: ## Download data from natural earth
	curl -o data/ne_50m_land.zip https://naturalearth.s3.amazonaws.com/50m_physical/ne_50m_land.zip
	unzip -o -d data/ne_50m_land data/ne_50m_land.zip
	curl -o data/ne_50m_lakes.zip https://naturalearth.s3.amazonaws.com/50m_physical/ne_50m_lakes.zip
	unzip -o -d data/ne_50m_lakes data/ne_50m_lakes.zip


world: world-light world-dark  ## Generates the world maps

world-light: ## Generates the world map in light-mode
	poetry run python new_caledonia_maps/world.py --light

world-dark: ## Generates the world map in dark-mode
	poetry run python new_caledonia_maps/world.py --dark

panama: panama-light panama-dark  ## Generates the orthographic maps

panama-light: ## Generates the orthographic map in light-mode
	poetry run python new_caledonia_maps/panama.py --light

panama-dark: ## Generates the orthographic map in dark-mode
	poetry run python new_caledonia_maps/panama.py --dark

lint: ## Checks for linting errors
	poetry run flake8

update-engraver: ## upgrades map-engraver to latest version of master
	poetry remove map-engraver || true
	poetry add git+https://github.com/leifgehrmann/map-engraver.git
	poetry install
