#!/bin/bash
# Build and push multi-arch Docker images to Docker Hub.
# Run from JKRiver/docker/:
#   ./build-and-push.sh [tag]          # e.g. ./build-and-push.sh 2.1.0
#   ./build-and-push.sh 2.1.0 latest   # push two tags at once
#
# Prerequisites:
#   docker login
#   docker buildx builder named "multi" with linux/amd64 + linux/arm64 support

set -e

REPO="wangjiake"
TAG="${1:-latest}"
EXTRA_TAG="${2:-}"
BUILDER="${BUILDER:-multi}"
PLATFORMS="linux/amd64,linux/arm64"

# Always run from JKRiver root regardless of where script is called from
cd "$(dirname "$0")/.."

build_push() {
  local name=$1
  local dockerfile=$2
  local context=$3
  local tags="-t ${REPO}/${name}:${TAG}"
  if [ -n "$EXTRA_TAG" ]; then
    tags="$tags -t ${REPO}/${name}:${EXTRA_TAG}"
  fi
  echo "=== Building & pushing ${name} (${PLATFORMS}) ==="
  docker buildx build \
    --builder "${BUILDER}" \
    --platform "${PLATFORMS}" \
    --push \
    $tags \
    -f "${dockerfile}" \
    "${context}"
}

build_push jkriver Dockerfile .

echo "=== Done ==="
echo "Images pushed:"
echo "  ${REPO}/jkriver:${TAG}${EXTRA_TAG:+ and :${EXTRA_TAG}}"
