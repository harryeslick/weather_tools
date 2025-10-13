# Tests for weather_tools

This directory contains pytest tests for the weather_tools package.

## Prerequisites

The tests assume the presence of SILO data in the following location:
```
~/Developer/DATA/silo_grids/
├── daily_rain/
├── evap_syn/
├── max_temp/
├── min_temp/
└── monthly_rain/
```

If this directory doesn't exist, the tests will be automatically skipped with a message indicating the missing data.

## Test Files

### `test_read_silo_simple.py`
Simple, fast smoke tests that verify basic functionality:
- Directory structure verification
- Basic data loading
- Single point extraction
- DataFrame conversion
- Coordinate range validation
- Data integrity checks

These tests are optimized for speed and memory usage by only loading small subsets of data.

### `test_read_silo_xarray.py`
Comprehensive test suite including:
- All basic tests from the simple suite
- Edge case handling
- Integration tests
- More extensive data validation

**Note**: Some tests in this file may require significant memory when loading full datasets.

## Running Tests

### Run all tests
```bash
uv run pytest tests/
```

### Run simple tests only
```bash
uv run pytest tests/test_read_silo_simple.py
```

### Run with verbose output
```bash
uv run pytest tests/ -v
```

### Run specific test
```bash
uv run pytest tests/test_read_silo_simple.py::test_extract_single_point -v
```

### Skip integration tests
```bash
uv run pytest tests/ -m "not integration"
```

### Run only integration tests
```bash
uv run pytest tests/ -m "integration"
```

## Test Coverage

To run tests with coverage:
```bash
uv run pytest tests/ --cov=src --cov-report=term-missing
```

## CI/CD

Tests are configured to run automatically in the CI/CD pipeline. If the SILO data directory is not available in the CI environment, tests will be skipped rather than failing.

## Writing New Tests

When adding new tests:
1. Use the `silo_data_available` fixture to ensure SILO data exists
2. Close datasets after use to free memory: `ds.close()`
3. Work with small data subsets for faster tests
4. Use `pytest.mark.integration` for tests that require full datasets
5. Add descriptive docstrings to explain what each test validates

Example:
```python
def test_my_feature(silo_data_available):
    """Test that my feature works correctly."""
    ds = read_silo_xarray(variables=["max_temp"], silo_dir=silo_data_available)
    
    # Test code here
    
    ds.close()  # Important: clean up
```
