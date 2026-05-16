#!/usr/bin/env python
"""
Discover and run tests for all Lambda functions.
Exits with status 0 if all tests pass, 1 if any fail.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / "app"


def find_lambda_functions():
    """Find all directories containing lambda_function.py"""
    lambdas = []
    for lambda_dir in APP_DIR.iterdir():
        if lambda_dir.is_dir():
            lambda_file = lambda_dir / "lambda_function.py"
            if lambda_file.exists():
                lambdas.append(lambda_dir)
    return sorted(lambdas)


def run_command(cmd, cwd=None):
    """Run a shell command and return success status."""
    print(f"→ {' '.join(cmd)}")
    try:
        subprocess.check_call(cmd, cwd=cwd)
        return True
    except subprocess.CalledProcessError:
        return False


def install_dependencies(lambda_dir):
    """Install test dependencies, handling different environment configurations."""
    test_req = lambda_dir / "requirements-test.txt"
    if not test_req.exists():
        return True
    
    print(f"\n📦 Installing test dependencies...")
    
    # Try with --break-system-packages for externally-managed environments
    cmd = ["pip", "install", "-q", "-r", "requirements-test.txt", "--break-system-packages"]
    if run_command(cmd, cwd=lambda_dir):
        return True
    
    # Fallback: try without the flag
    cmd = ["pip", "install", "-q", "-r", "requirements-test.txt"]
    return run_command(cmd, cwd=lambda_dir)


def main():
    lambdas = find_lambda_functions()
    
    if not lambdas:
        print("❌ No Lambda functions found in app/")
        return 1
    
    print(f"✓ Found {len(lambdas)} Lambda function(s):")
    for lambda_dir in lambdas:
        print(f"  - {lambda_dir.name}")
    print()
    
    all_passed = True
    
    for lambda_dir in lambdas:
        test_files = list(lambda_dir.glob("test_*.py"))
        
        if not test_files:
            print(f"⊘ {lambda_dir.name}: No tests found (skipped)")
            continue
        
        print(f"\n{'='*60}")
        print(f"Testing: {lambda_dir.name}")
        print(f"{'='*60}")
        
        # Install test dependencies
        if not install_dependencies(lambda_dir):
            print(f"❌ Failed to install test dependencies for {lambda_dir.name}")
            all_passed = False
            continue
        
        # Run pytest
        print(f"\n🧪 Running pytest...")
        if not run_command(["pytest", "-v"], cwd=lambda_dir):
            print(f"❌ Tests failed for {lambda_dir.name}")
            all_passed = False
        else:
            print(f"✓ Tests passed for {lambda_dir.name}")
    
    print(f"\n{'='*60}")
    if all_passed:
        print("✓ All Lambda functions passed tests!")
        print(f"{'='*60}\n")
        return 0
    else:
        print("❌ Some Lambda functions failed tests")
        print(f"{'='*60}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
