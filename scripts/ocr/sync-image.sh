#!/bin/bash
# Upload/download the mabi-ocr-models Docker image via rclone.
#
# The image bundles OCR models + essential data (dictionary, source_of_truth, fonts).
#
# Usage:
#   bash scripts/ocr/sync-image.sh upload     # save image → Google Drive
#   bash scripts/ocr/sync-image.sh download   # Google Drive → load image
#   bash scripts/ocr/sync-image.sh extract    # extract data/ from image to local project
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

REMOTE="gdrive:/ocr/docker"
IMAGE_NAME="mabi-ocr-models"
ARCHIVE="/tmp/${IMAGE_NAME}.tar.gz"

case "${1:-}" in
  upload)
    echo "==> Saving Docker image..."
    docker save "$IMAGE_NAME" | gzip > "$ARCHIVE"
    SIZE=$(du -h "$ARCHIVE" | cut -f1)
    echo "==> Uploading to Google Drive ($SIZE)..."
    rclone copy "$ARCHIVE" "$REMOTE" --progress
    rm -f "$ARCHIVE"
    echo "==> Done. Uploaded ${IMAGE_NAME} to ${REMOTE}/"
    ;;

  download)
    echo "==> Downloading from Google Drive..."
    rclone copy "${REMOTE}/${IMAGE_NAME}.tar.gz" /tmp/ --progress
    echo "==> Loading Docker image..."
    docker load < "$ARCHIVE"
    rm -f "$ARCHIVE"
    echo "==> Done. Image loaded:"
    docker images "$IMAGE_NAME" --format '  {{.Repository}}:{{.Tag}}  {{.Size}}'
    ;;

  extract)
    echo "==> Extracting data from ${IMAGE_NAME} image..."
    CID=$(docker create "$IMAGE_NAME")
    docker cp "$CID:/data/." "$PROJECT_ROOT/data/"
    docker cp "$CID:/models/." "$PROJECT_ROOT/backend/ocr/models/"
    docker rm "$CID" > /dev/null
    echo "==> Done. Extracted to:"
    echo "  data/dictionary/"
    echo "  data/source_of_truth/"
    echo "  data/fonts/"
    echo "  backend/ocr/models/"
    ;;

  *)
    echo "Usage: $0 {upload|download|extract}"
    echo ""
    echo "  upload    Save Docker image and upload to Google Drive"
    echo "  download  Download from Google Drive and load Docker image"
    echo "  extract   Extract models + data from image to local project"
    exit 1
    ;;
esac
