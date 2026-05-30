#!/usr/bin/env python
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / "app" / "lambdas" 
BUILD_DIR = ROOT / ".build" / "lambdas" 
PACKAGE_DIR = ROOT / ".package" / "lambdas" 
HASH_DIR = ROOT / ".hashes" / "lambdas" 


def run(cmd):
    print(f"-> {' '.join(cmd)}")
    subprocess.check_call(cmd)


def clean():
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    if PACKAGE_DIR.exists():
        shutil.rmtree(PACKAGE_DIR)
    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)

def save_hash(lambda_name: str, hash_value: str):
    HASH_DIR.mkdir(parents=True, exist_ok=True)
    (HASH_DIR / f"{lambda_name}.hash").write_text(hash_value)

def compute_lambda_hash(lambda_dir: Path) -> str:
    """Compute a stable hash of all files inside the lambda folder."""
    sha = hashlib.sha256()

    for path in sorted(lambda_dir.rglob("*")):
        if path.is_file():
            sha.update(path.name.encode())
            sha.update(path.read_bytes())

    return sha.hexdigest()

def load_previous_hash(lambda_name: str) -> str:
    hash_file = HASH_DIR / f"{lambda_name}.hash"
    if hash_file.exists():
        return hash_file.read_text().strip()
    return ""

def build_single_lambda(lambda_dir: Path):
    lambda_name = lambda_dir.name
    print(f"\n=== Checking Lambda: {lambda_name} ===")

    # 1. Compute hash
    new_hash = compute_lambda_hash(lambda_dir)
    old_hash = load_previous_hash(lambda_name)

    if new_hash == old_hash:
        print(f"⏩ No changes detected for {lambda_name}, skipping build")
        return

    print(f"🔨 Changes detected — rebuilding {lambda_name}")

    # 2. Prepare temp build dir
    temp_dir = BUILD_DIR / lambda_name
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    # 3. Install dependencies
    req = lambda_dir / "requirements.txt"
    if req.exists() and req.read_text().strip():
        print(f"Installing dependencies for {lambda_name}")
        run([sys.executable, "-m", "pip", "install", "-r", str(req), "-t", str(temp_dir)])
    else:
        print(f"No requirements.txt for {lambda_name}, skipping deps")

    # 4. Copy source
    for item in lambda_dir.iterdir():
        if item.name == "requirements.txt":
            continue
        dest = temp_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)

    # 5. Create ZIP
    zip_path = PACKAGE_DIR / f"{lambda_name}.zip"
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as zf:
        for path in temp_dir.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(temp_dir))

    print(f"Created {zip_path}")

    # 6. Save new hash
    save_hash(lambda_name, new_hash)
    print(f"Saved hash for {lambda_name}")

def main():
    # Do NOT clean everything — keep previous builds
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)
    HASH_DIR.mkdir(parents=True, exist_ok=True)

    for item in APP_DIR.iterdir():
        if item.is_dir():
            build_single_lambda(item)

    print("\n🎉 Incremental Lambda build complete!")


if __name__ == "__main__":
    main()
