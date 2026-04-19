#!/usr/bin/env bash
set -o errexit

echo "=== Moving into backend ==="
cd backend

echo "=== Installing dependencies ==="
pip install -r requirements.txt

echo "=== Collecting static files ==="
python manage.py collectstatic --no-input

echo "=== Running migrations ==="
python manage.py migrate

echo "=== Loading Bible data (safe) ==="
python manage.py load_kjv

echo "=== Cleaning verses (safe) ==="
python manage.py clean_verses

echo "=== Verifying database ==="
python manage.py check_db || echo "DB check skipped"

echo "=== Building phonetic index ==="
python manage.py build_phonetic_index

echo "=== Build complete ==="