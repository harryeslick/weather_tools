#!/bin/bash

pip install uv
uv venv .venv
uv pip install -r requirements.lock --no-cache --link-mode=copy
uv pip install -r requirements-dev.lock --no-cache --link-mode=copy
echo "source /workspaces/py_template/.venv/bin/activate" >> ~/.zshrc 

# pip install -r ./.devcontainer/dev_requirements.txt
# pip install -e .
