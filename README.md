# Weather tools

[![Deploy MkDocs GitHub Pages](https://github.com/harryeslick/weather_tools/actions/workflows/mkdocs.yml/badge.svg)](https://github.com/harryeslick/weather_tools/actions/workflows/mkdocs.yml)

This is a python package for personal commonly used functions for working with weather data.
Primarily for loading and using [SILO weather data](https://www.longpaddock.qld.gov.au/silo/gridded-data/) from local netCDF files.

To use this package you will need to download the netCDF files which you require from SILO.
A complete list of netCDF files available on AWS S3 can be found here:
<https://s3-ap-southeast-2.amazonaws.com/silo-open-data/Official/annual/index.html>

Package uses:

- `rye` for package and dependency management
- `uv` is used for dependencies within the dev container, using the `rye` `requirements.lock` file
- `mkdocs` for documentation with deployment via `gh_actions`
- `pytest` with `pytest-cov` for code coverage
- `pre-commit` used used to enforce code formatting using `ruff`, and spelling using `codespell`

## Project Organization

- `.github/workflows`: Contains GitHub Actions used for building, testing, and publishing.
- `.devcontainer/devcontainer.json`: Contains the configuration for the development container for VSCode, including  VSCode extensions to install.
- `.vscode/settings.json`: Contains VSCode settings specific to the project,
- `src`: Place new source code here.
- `tests`: Contains tests using `pytest`
- `pyproject.toml`: Contains metadata about the project and configurations for additional tools used to format, lint, type-check, and analyze Python code.

## Installation

### Local development

- setup environment `rye sync`
- setup pre-commit `pre-commit install-hooks`
