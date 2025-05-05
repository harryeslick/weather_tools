# Python Project Template

This is a repository template for building python projects.
It uses:

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

This template was originally based on Based on template from [Microsoft](https://github.com/microsoft/python-package-template)

## Using this template

- find and replace the project name `py_template` with new project name. 
- rename the python module dir `./src/py_template/` to match .
- update `docs/index.md`
- replace readme text
- change workspace `titleBar.activeBackground` in `./.vscode/settings.json`

## Installation
### Local development
- setup environment `rye sync`
- setup pre-commit `pre-commit install-hooks`

### Using VSCode DevContainer
- open project folder in vscode
- install VSCode Dev-container extension
- run / Build Dev-container
