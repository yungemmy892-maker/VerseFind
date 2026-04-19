#!/usr/bin/env bash
# Render runs this automatically on every deploy.
# Set as Build Command in Render dashboard (or render.yaml handles it).
set -o errexit

echo "=== Installing dependencies ==="
pip install -r requirements.txt

echo "=== Collecting static files ==="
python manage.py collectstatic --no-input

echo "=== Running migrations ==="
python manage.py migrate

echo "=== Cleaning verses ==="
python scripts/clean_verses.py

echo "=== Loading KJV data ==="
python scripts/load_kjv.py

echo "=== Verifying database ==="
python scripts/check_db.py

echo "=== Build complete ==="