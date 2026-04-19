"""
Run this to see exactly which books are missing from your database.

Usage:
    python scripts/check_db.py
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "versefind.settings")
import django
django.setup()

from bible.models import Verse, Book

EXPECTED = {
    "Genesis":50,"Exodus":40,"Leviticus":27,"Numbers":36,"Deuteronomy":34,
    "Joshua":24,"Judges":21,"Ruth":4,"1 Samuel":31,"2 Samuel":24,
    "1 Kings":22,"2 Kings":25,"1 Chronicles":29,"2 Chronicles":36,
    "Ezra":10,"Nehemiah":13,"Esther":10,"Job":42,"Psalms":150,
    "Proverbs":31,"Ecclesiastes":12,"Song of Solomon":8,"Isaiah":66,
    "Jeremiah":52,"Lamentations":5,"Ezekiel":48,"Daniel":12,"Hosea":14,
    "Joel":3,"Amos":9,"Obadiah":1,"Jonah":4,"Micah":7,"Nahum":3,
    "Habakkuk":3,"Zephaniah":3,"Haggai":2,"Zechariah":14,"Malachi":4,
    "Matthew":28,"Mark":16,"Luke":24,"John":21,"Acts":28,"Romans":16,
    "1 Corinthians":16,"2 Corinthians":13,"Galatians":6,"Ephesians":6,
    "Philippians":4,"Colossians":4,"1 Thessalonians":5,"2 Thessalonians":3,
    "1 Timothy":6,"2 Timothy":4,"Titus":3,"Philemon":1,"Hebrews":13,
    "James":5,"1 Peter":5,"2 Peter":3,"1 John":5,"2 John":1,
    "3 John":1,"Jude":1,"Revelation":22,
}

total_verses = Verse.objects.filter(version__code="KJV").count()
print(f"\nTotal KJV verses in DB: {total_verses} / 31102 expected")
print(f"{'='*55}")

missing_books = []
partial_books = []

for book_name, expected_chapters in EXPECTED.items():
    count = Verse.objects.filter(
        version__code="KJV",
        book__name=book_name
    ).count()

    if count == 0:
        missing_books.append(book_name)
        print(f"  MISSING  {book_name}")
    else:
        # Check chapters
        chapters_in_db = Verse.objects.filter(
            version__code="KJV",
            book__name=book_name
        ).values_list("chapter", flat=True).distinct().count()

        if chapters_in_db < expected_chapters:
            partial_books.append(book_name)
            print(f"  PARTIAL  {book_name}: {chapters_in_db}/{expected_chapters} chapters ({count} verses)")

print(f"\n{'='*55}")
print(f"Missing books:  {len(missing_books)}")
print(f"Partial books:  {len(partial_books)}")
print(f"Complete books: {66 - len(missing_books) - len(partial_books)}/66")

if missing_books or partial_books:
    print(f"\n→ Run: python scripts/load_kjv.py")
    print(f"  It will skip already-loaded verses and fill in the gaps.")
else:
    print(f"\n All 66 books fully loaded!")