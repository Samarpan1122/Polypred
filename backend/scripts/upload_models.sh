#!/usr/bin/env bash
set -euo pipefail

# Upload trained model weights from local directory → S3
# Usage: ./upload_models.sh <local_models_dir>

BUCKET="polypred-models-production"
PREFIX="models/"
LOCAL_DIR="${1:-.}"

echo "▶ Uploading model weights from $LOCAL_DIR → s3://$BUCKET/$PREFIX"

for f in "$LOCAL_DIR"/*.{pth,joblib,pkl}; do
  [ -f "$f" ] || continue
  filename=$(basename "$f")
  echo "  ↑ $filename"
  aws s3 cp "$f" "s3://$BUCKET/$PREFIX$filename"
done

echo "✓ Done. Files in S3:"
aws s3 ls "s3://$BUCKET/$PREFIX" --human-readable
