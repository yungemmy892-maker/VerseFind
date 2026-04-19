"""
One-time cleanup — strips Strong's concordance tags from all verses in the DB.

Strong's tags look like: <S>5315</S>
They get embedded in verse text from some Bible data sources and break matching.

Run once:
    python scripts/clean_verses.py
"""

import os
import sys
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "versefind.settings")
import django
django.setup()

import unicodedata
from bible.models import Verse


def clean_text(text):
    """Strip Strong's tags like <S>5315</S> and any other XML/HTML tags."""
    text = re.sub(r"<S>\d+</S>", "", text)   # Strong's specifically
    text = re.sub(r"<[^>]+>", "", text)       # any remaining tags
    text = re.sub(r"  +", " ", text).strip()
    return text


def normalize(text):
    text = clean_text(text)
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def main():
    print("Scanning for verses with Strong's tags...")

    # Find dirty verses — those containing <S> tags
    dirty = Verse.objects.filter(text__contains="<S>")
    total_dirty = dirty.count()

    if total_dirty == 0:
        print("vNo dirty verses found. All clean!")
        return

    print(f"Found {total_dirty} verses with tags. Cleaning...")

    batch = []
    cleaned = 0

    for verse in dirty.iterator(chunk_size=500):
        verse.text            = clean_text(verse.text)
        verse.normalized_text = normalize(verse.text)
        batch.append(verse)
        cleaned += 1

        if len(batch) >= 500:
            Verse.objects.bulk_update(batch, ["text", "normalized_text"])
            batch = []
            print(f"  Cleaned {cleaned}/{total_dirty}...", end="\r")

    if batch:
        Verse.objects.bulk_update(batch, ["text", "normalized_text"])

    print(f"\n Done! Cleaned {cleaned} verses.")

    # Verify
    still_dirty = Verse.objects.filter(text__contains="<S>").count()
    if still_dirty:
        print(f"⚠  {still_dirty} verses still have tags — run again.")
    else:
        print("All verses are now clean.")


if __name__ == "__main__":
    main()