# Exact SILO Station Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `silo search --station CODE --details` with a consistently formatted exact lookup at `silo search --station CODE`.

**Planning Mode:** Strict TDD

**Architecture:** Keep SILO's dedicated ID endpoint for exact lookup, normalize its headerless response in the existing station parser, and pass the resulting DataFrame through the CLI's established output path. Radius remains the discriminator for nearby searches.

**Tech Stack:** Python 3.12+, pandas, Pydantic, Typer, pytest, uv, Ruff

---

### Task 1: Normalize SILO ID metadata

**Files:**
- Modify: `tests/test_silo_api.py`
- Modify: `src/weather_tools/silo_api.py`

- [x] Add a test asserting that a headerless `SiloFormat.ID` response produces one row with `station_code`, `name`, `latitude`, `longitude`, `state`, and `elevation`.
- [x] Run the focused test and confirm it fails because ID responses currently become a one-column DataFrame.
- [x] Add ID handling to `_response_to_dataframe()` and `parse_station_data()` while retaining NAME and NEAR behavior.
- [x] Run the focused parser tests and confirm they pass.

### Task 2: Simplify the CLI contract

**Files:**
- Create: `tests/test_cli_silo.py`
- Modify: `src/weather_tools/cli/silo.py`

- [x] Add CLI tests asserting that bare `--station` constructs an ID query, renders canonical columns, and that `--details` is rejected.
- [x] Run the focused CLI tests and confirm the bare-station behavior fails before implementation.
- [x] Remove the `details` option and make `station` without `radius` select the exact lookup branch.
- [x] Route exact lookup output through the same DataFrame table/CSV handling as other searches.
- [x] Run the focused CLI tests and confirm they pass.

### Task 3: Update documentation

**Files:**
- Modify: `README.md`
- Modify: `CLI_README.md`
- Modify: `docs/cli.md`
- Modify: `docs/cli_reference.md`
- Modify: `docs/silo_api.md`

- [x] Replace `--station CODE --details` examples and option descriptions with bare exact station lookup examples.
- [x] Confirm `rg -n -- '--details' README.md CLI_README.md docs src tests` returns only the intentional rejection test, if any.

### Task 4: Increment version to 0.3.0

**Files:**
- Modify: `src/weather_tools/__init__.py`
- Modify: `CHANGELOG.md`

- [x] Add a `0.3.0` release entry dated 2026-08-14 describing the changed station lookup and removed option.
- [x] Change `__version__` from `0.2.0` to `0.3.0`.
- [x] Verify `weather-tools --version` reports `0.3.0`.

### Task 5: Verify the change

**Files:**
- Verify all modified files

- [x] Run `uv run pytest tests/ -m "not integration"` and confirm zero failures.
- [x] Run `ruff check .` and format-check the changed Python files.
- [x] Run CLI help and focused mocked CLI tests to verify `--details` is absent and exact lookup formatting is stable.
- [x] Review `git diff --check` and the final diff for unintended changes.
