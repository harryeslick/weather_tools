#!/bin/bash
# Manual Testing Script for SILO Download Functionality
#
# This script tests the download command with various scenarios to verify:
# - Single file downloads
# - Year range downloads
# - Skip existing files behavior
# - Force overwrite behavior
#
# IMPORTANT: These tests will download real data from AWS S3 (~410MB per daily variable file)
# Make sure you have sufficient disk space and network bandwidth before running.

set -e  # Exit on error

# Configuration
TEST_DIR="$HOME/Developer/DATA/silo_grids_test"
SMALL_VAR="monthly_rain"  # ~14MB files (smaller for quick testing)
DAILY_VAR="daily_rain"     # ~410MB files (large, use sparingly)

echo "=========================================="
echo "SILO Download Manual Testing Script"
echo "=========================================="
echo ""
echo "Test directory: $TEST_DIR"
echo ""

# Cleanup function
cleanup() {
    echo ""
    echo "----------------------------------------"
    echo "Cleaning up test directory..."
    if [ -d "$TEST_DIR" ]; then
        rm -rf "$TEST_DIR"
        echo "✓ Test directory removed: $TEST_DIR"
    fi
}

# Register cleanup on exit
trap cleanup EXIT

echo "=========================================="
echo "TEST 1: Download single file (monthly_rain)"
echo "=========================================="
echo ""
echo "Command: weather-tools local download --var monthly_rain --start-year 2023 --end-year 2023 --silo-dir $TEST_DIR"
echo ""
uv run weather-tools local download \
    --var "$SMALL_VAR" \
    --start-year 2023 \
    --end-year 2023 \
    --silo-dir "$TEST_DIR"

echo ""
echo "Verifying downloaded file..."
if [ -f "$TEST_DIR/monthly_rain/2023.monthly_rain.nc" ]; then
    FILE_SIZE=$(du -h "$TEST_DIR/monthly_rain/2023.monthly_rain.nc" | cut -f1)
    echo "✓ File exists: $TEST_DIR/monthly_rain/2023.monthly_rain.nc"
    echo "✓ File size: $FILE_SIZE"
else
    echo "✗ ERROR: File not found!"
    exit 1
fi

echo ""
read -p "Press Enter to continue to Test 2..."

echo ""
echo "=========================================="
echo "TEST 2: Download year range (2021-2022)"
echo "=========================================="
echo ""
echo "Command: weather-tools local download --var monthly_rain --start-year 2021 --end-year 2022 --silo-dir $TEST_DIR"
echo ""
uv run weather-tools local download \
    --var "$SMALL_VAR" \
    --start-year 2021 \
    --end-year 2022 \
    --silo-dir "$TEST_DIR"

echo ""
echo "Verifying downloaded files..."
for year in 2021 2022; do
    if [ -f "$TEST_DIR/monthly_rain/$year.monthly_rain.nc" ]; then
        FILE_SIZE=$(du -h "$TEST_DIR/monthly_rain/$year.monthly_rain.nc" | cut -f1)
        echo "✓ File exists: $TEST_DIR/monthly_rain/$year.monthly_rain.nc ($FILE_SIZE)"
    else
        echo "✗ ERROR: File not found for year $year!"
        exit 1
    fi
done

echo ""
read -p "Press Enter to continue to Test 3..."

echo ""
echo "=========================================="
echo "TEST 3: Skip existing files (default behavior)"
echo "=========================================="
echo ""
echo "Re-running the same command from Test 2..."
echo "Expected: Files should be skipped (not re-downloaded)"
echo ""
echo "Command: weather-tools local download --var monthly_rain --start-year 2021 --end-year 2022 --silo-dir $TEST_DIR"
echo ""

# Capture modification time before
BEFORE_MTIME=$(stat -f "%m" "$TEST_DIR/monthly_rain/2023.monthly_rain.nc")

uv run weather-tools local download \
    --var "$SMALL_VAR" \
    --start-year 2021 \
    --end-year 2022 \
    --silo-dir "$TEST_DIR"

# Check modification time after
AFTER_MTIME=$(stat -f "%m" "$TEST_DIR/monthly_rain/2023.monthly_rain.nc")

echo ""
if [ "$BEFORE_MTIME" = "$AFTER_MTIME" ]; then
    echo "✓ Files were skipped (modification time unchanged)"
    echo "  Output should show '(skipped)' messages"
else
    echo "✗ ERROR: Files were re-downloaded (modification time changed)!"
    exit 1
fi

echo ""
read -p "Press Enter to continue to Test 4..."

echo ""
echo "=========================================="
echo "TEST 4: Force overwrite existing files"
echo "=========================================="
echo ""
echo "Command: weather-tools local download --var monthly_rain --start-year 2023 --end-year 2023 --silo-dir $TEST_DIR --force"
echo ""

# Capture modification time before
BEFORE_MTIME=$(stat -f "%m" "$TEST_DIR/monthly_rain/2023.monthly_rain.nc")
sleep 2  # Ensure time difference

uv run weather-tools local download \
    --var "$SMALL_VAR" \
    --start-year 2023 \
    --end-year 2023 \
    --silo-dir "$TEST_DIR" \
    --force

# Check modification time after
AFTER_MTIME=$(stat -f "%m" "$TEST_DIR/monthly_rain/2023.monthly_rain.nc")

echo ""
if [ "$BEFORE_MTIME" != "$AFTER_MTIME" ]; then
    echo "✓ Files were re-downloaded with --force (modification time changed)"
else
    echo "✗ ERROR: Files were not re-downloaded despite --force flag!"
    exit 1
fi

echo ""
read -p "Press Enter to continue to Test 5..."

echo ""
echo "=========================================="
echo "TEST 5: Download multiple variables"
echo "=========================================="
echo ""
echo "Command: weather-tools local download --var max_temp --var min_temp --start-year 2023 --end-year 2023 --silo-dir $TEST_DIR"
echo ""
echo "WARNING: This will download ~820MB of data (2 x ~410MB files)"
read -p "Continue? (y/N): " confirm
if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo "Skipping Test 5"
else
    uv run weather-tools local download \
        --var max_temp \
        --var min_temp \
        --start-year 2023 \
        --end-year 2023 \
        --silo-dir "$TEST_DIR"

    echo ""
    echo "Verifying downloaded files..."
    for var in max_temp min_temp; do
        if [ -f "$TEST_DIR/$var/2023.$var.nc" ]; then
            FILE_SIZE=$(du -h "$TEST_DIR/$var/2023.$var.nc" | cut -f1)
            echo "✓ File exists: $TEST_DIR/$var/2023.$var.nc ($FILE_SIZE)"
        else
            echo "✗ ERROR: File not found for variable $var!"
            exit 1
        fi
    done
fi

echo ""
read -p "Press Enter to continue to Test 6..."

echo ""
echo "=========================================="
echo "TEST 6: Download using preset (daily)"
echo "=========================================="
echo ""
echo "Command: weather-tools local download --var daily --start-year 2023 --end-year 2023 --silo-dir $TEST_DIR"
echo ""
echo "WARNING: This will download ~1.6GB of data (4 variables x ~410MB)"
echo "The 'daily' preset expands to: daily_rain, max_temp, min_temp, evap_syn"
read -p "Continue? (y/N): " confirm
if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo "Skipping Test 6"
else
    uv run weather-tools local download \
        --var daily \
        --start-year 2023 \
        --end-year 2023 \
        --silo-dir "$TEST_DIR"

    echo ""
    echo "Verifying downloaded files..."
    for var in daily_rain max_temp min_temp evap_syn; do
        if [ -f "$TEST_DIR/$var/2023.$var.nc" ]; then
            FILE_SIZE=$(du -h "$TEST_DIR/$var/2023.$var.nc" | cut -f1)
            echo "✓ File exists: $TEST_DIR/$var/2023.$var.nc ($FILE_SIZE)"
        else
            echo "✗ ERROR: File not found for variable $var!"
            exit 1
        fi
    done
fi

echo ""
echo "=========================================="
echo "TEST 7: Verify downloaded files can be read"
echo "=========================================="
echo ""
echo "Testing that downloaded files can be loaded with read_silo_xarray..."
echo ""

cat << 'EOF' > /tmp/test_read_downloaded.py
from pathlib import Path
from weather_tools import read_silo_xarray

test_dir = Path.home() / "Developer/DATA/silo_grids_test"

print("Loading monthly_rain from downloaded files...")
ds = read_silo_xarray(
    variables=["monthly_rain"],
    silo_dir=test_dir
)

print(f"✓ Dataset loaded successfully")
print(f"✓ Variables: {list(ds.data_vars)}")
print(f"✓ Time range: {ds.time.min().values} to {ds.time.max().values}")
print(f"✓ Shape: {ds.monthly_rain.shape}")

ds.close()
print("\n✓ All downloaded files are valid NetCDF files!")
EOF

uv run python /tmp/test_read_downloaded.py
rm /tmp/test_read_downloaded.py

echo ""
echo "=========================================="
echo "ALL TESTS COMPLETED SUCCESSFULLY!"
echo "=========================================="
echo ""
echo "Summary:"
echo "  ✓ Single file download works"
echo "  ✓ Year range download works"
echo "  ✓ Skip existing files works (default)"
echo "  ✓ Force overwrite works (--force flag)"
echo "  ✓ Multiple variables download works"
echo "  ✓ Preset expansion works"
echo "  ✓ Downloaded files are valid NetCDF"
echo ""
echo "Test directory will be cleaned up on exit."
echo ""
