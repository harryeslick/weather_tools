#!/usr/bin/env python3
"""Test script to demonstrate the weather-tools CLI functionality."""

import subprocess
import sys


def run_command(cmd):
    """Run a command and print the output."""
    print(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print("STDOUT:")
        print(result.stdout)
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {e}")
        print("STDOUT:")
        print(e.stdout)
        print("STDERR:")
        print(e.stderr)
        return False

def main():
    """Test the CLI functionality."""
    print("Testing weather-tools CLI")
    print("=" * 50)
    
    # Test help command
    print("\n1. Testing help command:")
    run_command([sys.executable, "-m", "weather_tools.cli", "--help"])
    
    # Test info command
    print("\n2. Testing info command:")
    run_command([sys.executable, "-m", "weather_tools.cli", "info", "--help"])
    
    # Test extract command help
    print("\n3. Testing extract command help:")
    run_command([sys.executable, "-m", "weather_tools.cli", "extract", "--help"])
    
    print("\n" + "=" * 50)
    print("CLI tests completed!")
    print("\nTo use the CLI after installation:")
    print("  weather-tools --help")
    print("  weather-tools info")
    print("  weather-tools extract --lat -27.5 --lon 153.0 --start-date 2020-01-01 --end-date 2025-01-01 --output weather.csv")

if __name__ == "__main__":
    main()