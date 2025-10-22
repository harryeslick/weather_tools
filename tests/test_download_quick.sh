#!/bin/bash
# Quick Download Test - Small file only (~14MB)
#
# This is a minimal test script that downloads a single small file
# to quickly verify the download functionality works.
#
# For comprehensive testing, use test_download_manual.sh

set -e

TEST_DIR="$HOME/Developer/DATA/silo_grids_test_quick"

echo "=========================================="
echo "Quick SILO Download Test"
echo "=========================================="
echo ""
echo "This will download one small file (~14MB) to test the download functionality."
echo "Test directory: $TEST_DIR"
echo ""

# Cleanup function
cleanup() {
    echo ""
    echo "Cleaning up test directory..."
    if [ -d "$TEST_DIR" ]; then
        rm -rf "$TEST_DIR"
        echo "✓ Test directory removed"
    fi
}

trap cleanup EXIT

echo "Downloading monthly_rain for 2023..."
echo ""

uv run weather-tools local download \
    --var monthly_rain \
    --start-year 2023 \
    --end-year 2023 \
    --silo-dir "$TEST_DIR"

echo ""
echo "Verifying file..."

if [ -f "$TEST_DIR/monthly_rain/2023.monthly_rain.nc" ]; then
    FILE_SIZE=$(du -h "$TEST_DIR/monthly_rain/2023.monthly_rain.nc" | cut -f1)
    echo "✓ File downloaded: $TEST_DIR/monthly_rain/2023.monthly_rain.nc"
    echo "✓ File size: $FILE_SIZE"
    echo ""
    echo "Testing that file can be read..."

    cat << 'EOF' > /tmp/test_read_quick.py
from pathlib import Path
from weather_tools import read_silo_xarray

test_dir = Path.home() / "Developer/DATA/silo_grids_test_quick"
ds = read_silo_xarray(variables=["monthly_rain"], silo_dir=test_dir)
print(f"✓ Dataset loaded: {list(ds.data_vars)}")
print(f"✓ Time range: {ds.time.min().values} to {ds.time.max().values}")
ds.close()
EOF

    uv run python /tmp/test_read_quick.py
    # rm /tmp/test_read_quick.py

    echo ""
    echo "=========================================="
    echo "✓ QUICK TEST PASSED!"
    echo "=========================================="
    echo ""
    echo "Download functionality is working correctly."
    echo "For comprehensive testing, run: ./test_download_manual.sh"
else
    echo "✗ ERROR: File not found!"
    exit 1
fi
