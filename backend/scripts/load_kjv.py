"""
Load KJV Bible data into the database from multiple sources.
"""

import os
import sys
import json
import re
import unicodedata
import urllib.request

# ---------------- DJANGO SETUP ---------------- #

if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "versefind.settings")
    import django
    django.setup()

from bible.models import BibleVersion, Book, Verse

# ---------------- CONFIG ---------------- #

BOOK_ORDER = [
    "Genesis","Exodus","Leviticus","Numbers","Deuteronomy","Joshua","Judges",
    "Ruth","1 Samuel","2 Samuel","1 Kings","2 Kings","1 Chronicles","2 Chronicles",
    "Ezra","Nehemiah","Esther","Job","Psalms","Proverbs","Ecclesiastes",
    "Song of Solomon","Isaiah","Jeremiah","Lamentations","Ezekiel","Daniel",
    "Hosea","Joel","Amos","Obadiah","Jonah","Micah","Nahum","Habakkuk",
    "Zephaniah","Haggai","Zechariah","Malachi",
    "Matthew","Mark","Luke","John","Acts","Romans","1 Corinthians","2 Corinthians",
    "Galatians","Ephesians","Philippians","Colossians","1 Thessalonians",
    "2 Thessalonians","1 Timothy","2 Timothy","Titus","Philemon","Hebrews",
    "James","1 Peter","2 Peter","1 John","2 John","3 John","Jude","Revelation",
]

OT_BOOKS = set(BOOK_ORDER[:39])

# ---------------- HELPERS ---------------- #

def normalize(text: str) -> str:
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def create_books():
    books = {}
    for i, name in enumerate(BOOK_ORDER, 1):
        book, _ = Book.objects.get_or_create(
            name=name,
            defaults={
                "abbreviation": name[:3],
                "testament": "OT" if name in OT_BOOKS else "NT",
                "order": i,
            },
        )
        books[name] = book
    return books


# ---------------- API LOADERS ---------------- #

def load_from_bolls():
    """
    Correct bolls.life loader (chapter-by-chapter)
    """
    print("\nTrying bolls.life (fixed)...")

    version, _ = BibleVersion.objects.get_or_create(
        code="KJV",
        defaults={"name": "King James Version", "language": "English"},
    )

    books = create_books()
    total_created = 0

    try:
        for book_name in BOOK_ORDER:
            print(f"  → {book_name}")

            chapter = 1

            while True:
                try:
                    url = f"https://bolls.life/get-chapter/KJV/{book_name}/{chapter}/"
                    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})

                    with urllib.request.urlopen(req, timeout=10) as response:
                        data = json.loads(response.read().decode("utf-8"))

                    # Stop if no verses
                    if not data or "verses" not in data:
                        break

                    verses = data["verses"]
                    if not verses:
                        break

                    to_create = []

                    for v in verses:
                        text = v.get("text", "").strip()

                        to_create.append(Verse(
                            version=version,
                            book=books[book_name],
                            chapter=chapter,
                            verse_number=v.get("verse"),
                            text=text,
                            normalized_text=normalize(text),
                        ))

                    Verse.objects.bulk_create(to_create, ignore_conflicts=True)
                    total_created += len(to_create)

                    chapter += 1

                except Exception:
                    break  # no more chapters

            print(f"    ✓ Done {book_name}")

        print(f"\nLoaded {total_created} verses from bolls.life")
        return total_created > 0

    except Exception as e:
        print(f"  ✗ bolls.life failed: {e}")
        return False


def load_from_bible_api():
    """
    Fixed bible-api loader (chapter-by-chapter fallback)
    """
    print("\nTrying bible-api.com (fallback)...")

    version, _ = BibleVersion.objects.get_or_create(
        code="KJV",
        defaults={"name": "King James Version", "language": "English"},
    )

    books = create_books()
    total_created = 0

    # Limit fallback scope (avoid long runtime)
    fallback_books = ["John", "Genesis", "Matthew"]

    for book_name in fallback_books:
        print(f"  → {book_name}")

        chapter = 1

        while True:
            try:
                url = f"https://bible-api.com/{book_name}%20{chapter}?translation=kjv"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})

                with urllib.request.urlopen(req, timeout=10) as response:
                    data = json.loads(response.read().decode("utf-8"))

                verses = data.get("verses", [])
                if not verses:
                    break

                to_create = []

                for v in verses:
                    text = v["text"].strip()

                    to_create.append(Verse(
                        version=version,
                        book=books[book_name],
                        chapter=v["chapter"],
                        verse_number=v["verse"],
                        text=text,
                        normalized_text=normalize(text),
                    ))

                Verse.objects.bulk_create(to_create, ignore_conflicts=True)
                total_created += len(to_create)

                chapter += 1

            except Exception:
                break

        print(f"    ✓ Done {book_name}")

    print(f"\nLoaded {total_created} verses from bible-api")
    return total_created > 0


def load_fallback_test_data():
    print("\n⚠️ Using minimal test data...")

    version, _ = BibleVersion.objects.get_or_create(
        code="KJV",
        defaults={"name": "King James Version", "language": "English"},
    )

    books = create_books()

    samples = [
        ("John", 3, 16, "For God so loved the world..."),
        ("Genesis", 1, 1, "In the beginning..."),
    ]

    for b, c, v, t in samples:
        Verse.objects.get_or_create(
            version=version,
            book=books[b],
            chapter=c,
            verse_number=v,
            defaults={
                "text": t,
                "normalized_text": normalize(t)
            },
        )

# ---------------- MAIN ---------------- #

def main():
    print("=" * 50)
    print("Loading KJV Bible Data")
    print("=" * 50)

    if load_from_bolls():
        print("\n✅ Loaded via bolls.life")
        return

    if load_from_bible_api():
        print("\n✅ Loaded via bible-api")
        return

    load_fallback_test_data()


if __name__ == "__main__":
    main()