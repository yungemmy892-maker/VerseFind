#!/usr/bin/env bash
set -o errexit

echo "=== Collecting static files ==="
python manage.py collectstatic --no-input

echo "=== Running migrations ==="
python manage.py migrate

echo "=== Loading Bible data (safe) ==="
python manage.py load_kjv

echo "=== Cleaning verses ===" 
python manage.py clean_verses

echo "=== Verifying database ===" 
python manage.py check_db

echo "=== Building phonetic index ==="
python manage.py build_phonetic_index

echo "=== Build complete ==="