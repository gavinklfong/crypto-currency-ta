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
ZIP_PATH = ROOT / "deployment.zip"


def run(cmd):
    print(f"-> {' '.join(cmd)}")
    subprocess.check_call(cmd)


def clean():
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()


def install_deps():
    req = APP_DIR / "requirements.txt"
    if not req.exists() or req.read_text().strip() == "":
        print("No requirements or empty requirements.txt, skipping deps")
        return
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    run([sys.executable, "-m", "pip", "install", "-r", str(req), "-t", str(BUILD_DIR)])


def copy_app():
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    for item in APP_DIR.iterdir():
        if item.name == "requirements.txt":
            continue
        dest = BUILD_DIR / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)


def make_zip():
    with ZipFile(ZIP_PATH, "w", ZIP_DEFLATED) as zf:
        for path in BUILD_DIR.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(BUILD_DIR))
    print(f"Created {ZIP_PATH}")


if __name__ == "__main__":
    clean()
    install_deps()
    copy_app()
    make_zip()
