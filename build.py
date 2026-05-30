#!/usr/bin/env python3
import subprocess
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent

BUILD_LAYERS = ROOT / "build_layers.py"
BUILD_LAMBDAS = ROOT / "build_lambdas.py"

def run(title, script):
    print(f"\n=== {title} ===")
    if not script.exists():
        print(f"Skipping: {script.name} not found")
        return

    try:
        subprocess.check_call([sys.executable, str(script)])
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running {script.name}")
        raise e

def main():
    print("🚀 Starting full build pipeline")

    # 1. Build layers first
    run("Building Lambda Layers", BUILD_LAYERS)

    # 2. Build lambdas
    run("Building Lambda Functions", BUILD_LAMBDAS)

    print("\n🎉 Build complete — all layers and lambdas are up to date")

if __name__ == "__main__":
    main()
