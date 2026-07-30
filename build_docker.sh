#!/bin/bash
set -e

IMAGE_NAME="gomoku-server"
IMAGE_TAG="latest"
FULL_IMAGE="${IMAGE_NAME}:${IMAGE_TAG}"

echo "============================================"
echo "  Building Gomoku Server Docker Image"
echo "============================================"
echo ""

# Check if docker is available
if ! command -v docker &> /dev/null; then
    echo "[ERROR] Docker is not installed or not in PATH"
    echo "Install Docker Desktop from: https://www.docker.com/products/docker-desktop/"
    exit 1
fi

echo "[1/3] Building image..."
cd "$(dirname "$0")/server"
docker build -t "${FULL_IMAGE}" .

echo ""
echo "[2/3] Image built successfully!"
docker images "${FULL_IMAGE}"

echo ""
echo "[3/3] Quick start commands:"
echo ""
echo "  Run container (port 8080):"
echo "    docker run -d -p 8080:8080 --name gomoku-server --restart unless-stopped ${FULL_IMAGE}"
echo ""
echo "  Or use docker-compose:"
echo "    docker-compose up -d"
echo ""
echo "  Check logs:"
echo "    docker logs -f gomoku-server"
echo ""
echo "  Stop container:"
echo "    docker stop gomoku-server"
echo ""
echo "============================================"
echo "  Build complete!"
echo "============================================"