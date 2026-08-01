#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ZIP="$SCRIPT_DIR/common-utils.zip"
rm -f "$ZIP"

PYTHON_DIR="$SCRIPT_DIR/python"

# Lambda layers for Python need a python/ directory at ZIP root.
# Lambda mounts the layer at /opt/python and adds /opt/python to sys.path,
# so python/common_utils/ in the ZIP becomes importable as common_utils.
(cd "$SCRIPT_DIR" && zip -r "$ZIP" python -x "python/__pycache__/*")

echo "✓ Built $ZIP"
