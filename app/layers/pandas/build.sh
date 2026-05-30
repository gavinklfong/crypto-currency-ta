#!/bin/bash
set -e

LAYER_NAME="pandas_layer"
IMAGE_NAME="build-pandas"

docker build -t $IMAGE_NAME .

CONTAINER_ID=$(docker create $IMAGE_NAME)
docker cp $CONTAINER_ID:/opt/python ./python
docker rm $CONTAINER_ID

# Clean up
find python -type d -name "__pycache__" -exec rm -rf {} +
find python -type d -name "tests" -exec rm -rf {} +
find python -type d -name "*.dist-info" -exec rm -rf {} +

zip -r -9 ${LAYER_NAME}.zip python
rm -rf python

echo "Built ${LAYER_NAME}.zip"
