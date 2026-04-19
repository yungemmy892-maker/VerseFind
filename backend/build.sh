#!/usr/bin/env bash
# Render runs this automatically on every deploy.
# Set as Build Command in Render dashboard (or render.yaml handles it).

set -o errexit   # exit immediately if any command fails

echo "=== Installing dependencies ==="
pip install -r requirements.txt

echo "=== Collecting static files ==="
python manage.py collectstatic --no-input

echo "=== Running migrations ==="
python manage.py migrate

echo "=== Build complete ==="