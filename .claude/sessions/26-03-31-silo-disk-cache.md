# Session: 26-03-31 — Persistent Disk Cache for SiloAPI

## Scope
Replace SiloAPI's in-memory dict cache with a persistent SQLite-backed disk cache using `diskcache`, enabling cross-instance and cross-session cache sharing.

## Key Changes
- **pyproject.toml**: Added `diskcache>=5.6.0` dependency
- **config.py**: Added `get_cache_dir()` → `~/.cache/weather_tools` (override via `WEATHER_TOOLS_CACHE_DIR`)
- **silo_api.py**:
  - New constructor params: `cache_dir`, `cache_size_limit` (2 GB), `cache_ttl`
  - `_disk_cache` (diskcache.Cache) and `_mem_cache` (dict) backends
  - `_cache_get()` / `_cache_set()` abstraction methods with graceful error handling
  - Cache hit promoted to `logger.info` with clear message showing how to clear cache
  - New `get_cache_disk_usage()` method
  - `":memory:"` sentinel for old in-memory behaviour
- **cli/silo.py**:
  - `--cache-dir` option on `patched-point` and `data-drill` commands
  - Cache reporting shows entry count + disk usage + clear instructions
  - New `weather-tools silo cache` subcommand (`--info`, `--clear`)
- **CLAUDE.md**: Updated `silo_api.py` docs and CLI command listing

## Tests Run
- `tests/test_silo_cache.py`: 11 tests — persistence, cross-instance sharing, `:memory:` mode, disabled cache, clear, TTL expiry, disk usage, graceful degradation
- Full non-integration suite: 198 passed
- Ruff lint + format: clean

## Open Items
- MetNoAPI disk caching deferred (different TTL semantics for forecast data)
- CLI `--enable-cache` defaults to False; could consider defaulting to True now that cache is persistent
