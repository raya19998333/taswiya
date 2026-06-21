#!/usr/bin/env bash
set -e

# Render's build image mounts /var/lib/apt as read-only.
# Redirect apt state/cache to /tmp so package installation still works.
APT_STATE=/tmp/apt-state
APT_CACHE=/tmp/apt-cache
mkdir -p "$APT_STATE/lists/partial" "$APT_CACHE/archives/partial"

apt-get \
  -o Dir::State="$APT_STATE" \
  -o Dir::Cache="$APT_CACHE" \
  update -qq

apt-get \
  -o Dir::State="$APT_STATE" \
  -o Dir::Cache="$APT_CACHE" \
  install -y -q tesseract-ocr tesseract-ocr-ara

pip install -r requirements.txt
