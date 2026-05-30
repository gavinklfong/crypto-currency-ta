#!/usr/bin/env python3
import hashlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAYERS_DIR = ROOT / "app" / "layers"
OUTPUT_DIR = ROOT / ".package" / "layers"
HASH_DIR = ROOT / ".hashes" / "layers"

def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()

def compute_layer_hash(layer_dir: Path) -> str:
    """Hash all relevant build inputs."""
    h = hashlib.sha256()

    for filename in ["requirements.txt", "Dockerfile", "build.sh"]:
        file_path = layer_dir / filename
        if file_path.exists():
            h.update(file_hash(file_path).encode())

    return h.hexdigest()

def run(cmd, cwd=None):
    print(f"-> {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=cwd)

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    HASH_DIR.mkdir(parents=True, exist_ok=True)

    for layer_dir in LAYERS_DIR.iterdir():
        if not layer_dir.is_dir():
            continue

        layer_name = layer_dir.name
        build_script = layer_dir / "build.sh"

        if not build_script.exists():
            print(f"Skipping {layer_name}: no build.sh found")
            continue

        print(f"\n=== Checking layer: {layer_name} ===")

        # Compute current hash
        current_hash = compute_layer_hash(layer_dir)
        hash_file = HASH_DIR / f"{layer_name}.hash"

        # Check if hash matches previous build
        if hash_file.exists():
            previous_hash = hash_file.read_text().strip()
            if previous_hash == current_hash:
                print(f"✓ No changes detected — skipping build for {layer_name}")
                continue

        print(f"🔨 Changes detected — building layer: {layer_name}")

        # Run the layer's build script
        run(["bash", str(build_script)], cwd=layer_dir)

        # Find the produced ZIP
        zip_files = list(layer_dir.glob("*.zip"))
        if not zip_files:
            raise RuntimeError(f"No ZIP produced for layer {layer_name}")

        zip_path = zip_files[0]
        output_zip = OUTPUT_DIR / f"{layer_name}.zip"

        # Move ZIP to .package/layers/
        print(f"📦 Moving {zip_path.name} -> {output_zip}")
        zip_path.replace(output_zip)

        # Save new hash
        hash_file.write_text(current_hash)

        print(f"✓ Build complete for {layer_name}")

    print("\n🎉 All layers processed!")

if __name__ == "__main__":
    main()
