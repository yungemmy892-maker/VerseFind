#!/usr/bin/env bash
# Render runs this automatically on every deploy.
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

echo "=== Building phonetic index ==="
python manage.py build_phonetic_index

echo "=== Build complete ==="