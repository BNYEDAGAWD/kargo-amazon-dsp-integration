#!/bin/bash

# Docker build script with proper tagging and metadata
set -e

# Configuration
IMAGE_NAME="kargo-amazon-dsp-integration"
REGISTRY="${DOCKER_REGISTRY:-localhost}"
APP_VERSION="${APP_VERSION:-$(git describe --tags --always --dirty 2>/dev/null || echo 'dev')}"
BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
VCS_REF="${VCS_REF:-$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🐳 Building Docker image for Kargo Amazon DSP Integration${NC}"
echo -e "${YELLOW}Version: ${APP_VERSION}${NC}"
echo -e "${YELLOW}Build Date: ${BUILD_DATE}${NC}"
echo -e "${YELLOW}VCS Ref: ${VCS_REF}${NC}"

# Build the image
echo -e "${GREEN}📦 Building Docker image...${NC}"
docker build \
  --build-arg APP_VERSION="${APP_VERSION}" \
  --build-arg BUILD_DATE="${BUILD_DATE}" \
  --build-arg VCS_REF="${VCS_REF}" \
  --tag "${REGISTRY}/${IMAGE_NAME}:${APP_VERSION}" \
  --tag "${REGISTRY}/${IMAGE_NAME}:latest" \
  --file Dockerfile \
  .

echo -e "${GREEN}✅ Docker image built successfully!${NC}"

# Display image information
echo -e "${GREEN}📋 Image Information:${NC}"
docker images "${REGISTRY}/${IMAGE_NAME}" --format "table {{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.CreatedSince}}\t{{.Size}}"

# Optional: Run security scan
if command -v trivy >/dev/null 2>&1; then
    echo -e "${GREEN}🔍 Running security scan...${NC}"
    trivy image "${REGISTRY}/${IMAGE_NAME}:${APP_VERSION}"
fi

# Optional: Test the built image
if [ "${SKIP_TEST:-false}" != "true" ]; then
    echo -e "${GREEN}🧪 Testing built image...${NC}"
    
    # Start container for testing
    CONTAINER_ID=$(docker run -d \
        -e ENVIRONMENT=test \
        -e DATABASE_URL=sqlite:///tmp/test.db \
        -p 8000:8000 \
        "${REGISTRY}/${IMAGE_NAME}:${APP_VERSION}")
    
    # Wait for container to start
    sleep 10
    
    # Health check
    if curl -f http://localhost:8000/health/live >/dev/null 2>&1; then
        echo -e "${GREEN}✅ Health check passed${NC}"
    else
        echo -e "${RED}❌ Health check failed${NC}"
        docker logs "$CONTAINER_ID"
        exit 1
    fi
    
    # Stop test container
    docker stop "$CONTAINER_ID" >/dev/null
    docker rm "$CONTAINER_ID" >/dev/null
    
    echo -e "${GREEN}✅ Image test completed successfully${NC}"
fi

echo -e "${GREEN}🎉 Build completed successfully!${NC}"
echo -e "${YELLOW}To run the image:${NC}"
echo -e "  docker run -p 8000:8000 ${REGISTRY}/${IMAGE_NAME}:${APP_VERSION}"
echo -e "${YELLOW}To push to registry:${NC}"
echo -e "  docker push ${REGISTRY}/${IMAGE_NAME}:${APP_VERSION}"