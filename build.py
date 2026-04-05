#!/usr/bin/env python
import os
import shutil
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / "app"
BUILD_DIR = ROOT / ".build"


def run(cmd):
    print(f"-> {' '.join(cmd)}")
    subprocess.check_call(cmd)


def clean():
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)


def build_single_lambda(lambda_dir: Path):
    lambda_name = lambda_dir.name
    print(f"\n=== Building Lambda: {lambda_name} ===")

    temp_dir = BUILD_DIR / lambda_name
    temp_dir.mkdir(parents=True, exist_ok=True)

    # 1. Install dependencies if requirements.txt exists
    req = lambda_dir / "requirements.txt"
    if req.exists() and req.read_text().strip():
        print(f"Installing dependencies for {lambda_name}")
        run([sys.executable, "-m", "pip", "install", "-r", str(req), "-t", str(temp_dir)])
    else:
        print(f"No requirements.txt for {lambda_name}, skipping deps")

    # 2. Copy source code
    for item in lambda_dir.iterdir():
        if item.name == "requirements.txt":
            continue
        dest = temp_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)

    # 3. Create ZIP
    zip_path = ROOT / f"deployment-{lambda_name}.zip"
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as zf:
        for path in temp_dir.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(temp_dir))

    print(f"Created {zip_path}")


def main():
    clean()

    # Build each subfolder under app/
    for item in APP_DIR.iterdir():
        if item.is_dir():
            build_single_lambda(item)

    print("\n🎉 All Lambda functions built successfully!")


if __name__ == "__main__":
    main()
