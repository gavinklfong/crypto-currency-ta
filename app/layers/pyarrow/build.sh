#!/bin/bash
set -e

LAYER_NAME="pyarrow_layer"
IMAGE_NAME="build-pyarrow"

docker build -t $IMAGE_NAME .

CONTAINER_ID=$(docker create $IMAGE_NAME)
docker cp $CONTAINER_ID:/opt/python ./python
docker rm $CONTAINER_ID

echo "🧹 Cleaning unnecessary files (safe mode)..."

# Remove Python cache
find python -type d -name "__pycache__" -exec rm -rf {} +

# Remove tests
find python -type d -name "tests" -exec rm -rf {} +
find python -type d -name "test" -exec rm -rf {} +

# Keep pyarrow metadata (required)
# Remove pandas metadata if present
find python -type d -name "pandas-*.dist-info" -exec rm -rf {} +

# echo "🔧 Removing optional Arrow components..."

# SAFE TO REMOVE:
# find python -type f -name "libarrow_flight.so*" -delete
# find python -type f -name "libarrow_python_flight.so*" -delete

# DO NOT REMOVE (required by pyarrow):
# libarrow.so
# libarrow_python.so
# libparquet.so
# libarrow_dataset.so

echo "🔧 Stripping large shared libraries (safe threshold)..."

find python -type f -name "*.so" -size +20000k -exec strip {} \; || true

echo "🗜️ Zipping layer with maximum compression..."
zip -r -9 ${LAYER_NAME}.zip python

rm -rf python

echo "✅ Layer built: ${LAYER_NAME}.zip"
