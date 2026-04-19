"""
Load KJV Bible data into the database.

Sources tried in order:
  1. bolls.life API  — uses numeric book ID (1-66), not book name
  2. bible-api.com   — full fallback for all 66 books
  3. GitHub raw JSON — aruljohn/Bible-kjv
  4. Local kjv.json  — manual download fallback

Run:
    python scripts/load_kjv.py
"""

import os
import sys
import json
import re
import unicodedata
import urllib.request
import time

# ── Django setup ──────────────────────────────────────────────────────────── #
if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "versefind.settings")
    import django
    django.setup()

from bible.models import BibleVersion, Book, Verse

# ── Book definitions ──────────────────────────────────────────────────────── #

BOOK_ORDER = [
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy",
    "Joshua", "Judges", "Ruth", "1 Samuel", "2 Samuel",
    "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles", "Ezra",
    "Nehemiah", "Esther", "Job", "Psalms", "Proverbs",
    "Ecclesiastes", "Song of Solomon", "Isaiah", "Jeremiah", "Lamentations",
    "Ezekiel", "Daniel", "Hosea", "Joel", "Amos",
    "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk",
    "Zephaniah", "Haggai", "Zechariah", "Malachi",
    "Matthew", "Mark", "Luke", "John", "Acts",
    "Romans", "1 Corinthians", "2 Corinthians", "Galatians", "Ephesians",
    "Philippians", "Colossians", "1 Thessalonians", "2 Thessalonians", "1 Timothy",
    "2 Timothy", "Titus", "Philemon", "Hebrews", "James",
    "1 Peter", "2 Peter", "1 John", "2 John", "3 John",
    "Jude", "Revelation",
]

# bolls.life needs the canonical number (1=Genesis ... 66=Revelation)
BOLLS_BOOK_ID = {name: idx for idx, name in enumerate(BOOK_ORDER, 1)}

# bible-api.com slugs
BIBLE_API_SLUG = {
    "Genesis":"genesis","Exodus":"exodus","Leviticus":"leviticus",
    "Numbers":"numbers","Deuteronomy":"deuteronomy","Joshua":"joshua",
    "Judges":"judges","Ruth":"ruth","1 Samuel":"1samuel","2 Samuel":"2samuel",
    "1 Kings":"1kings","2 Kings":"2kings","1 Chronicles":"1chronicles",
    "2 Chronicles":"2chronicles","Ezra":"ezra","Nehemiah":"nehemiah",
    "Esther":"esther","Job":"job","Psalms":"psalms","Proverbs":"proverbs",
    "Ecclesiastes":"ecclesiastes","Song of Solomon":"songofsolomon",
    "Isaiah":"isaiah","Jeremiah":"jeremiah","Lamentations":"lamentations",
    "Ezekiel":"ezekiel","Daniel":"daniel","Hosea":"hosea","Joel":"joel",
    "Amos":"amos","Obadiah":"obadiah","Jonah":"jonah","Micah":"micah",
    "Nahum":"nahum","Habakkuk":"habakkuk","Zephaniah":"zephaniah",
    "Haggai":"haggai","Zechariah":"zechariah","Malachi":"malachi",
    "Matthew":"matthew","Mark":"mark","Luke":"luke","John":"john",
    "Acts":"acts","Romans":"romans","1 Corinthians":"1corinthians",
    "2 Corinthians":"2corinthians","Galatians":"galatians",
    "Ephesians":"ephesians","Philippians":"philippians",
    "Colossians":"colossians","1 Thessalonians":"1thessalonians",
    "2 Thessalonians":"2thessalonians","1 Timothy":"1timothy",
    "2 Timothy":"2timothy","Titus":"titus","Philemon":"philemon",
    "Hebrews":"hebrews","James":"james","1 Peter":"1peter",
    "2 Peter":"2peter","1 John":"1john","2 John":"2john",
    "3 John":"3john","Jude":"jude","Revelation":"revelation",
}

CHAPTER_COUNTS = {
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

OT_BOOKS = set(BOOK_ORDER[:39])

ABBREVIATIONS = {
    "Genesis":"Gen","Exodus":"Exo","Leviticus":"Lev","Numbers":"Num",
    "Deuteronomy":"Deu","Joshua":"Jos","Judges":"Jdg","Ruth":"Rut",
    "1 Samuel":"1Sa","2 Samuel":"2Sa","1 Kings":"1Ki","2 Kings":"2Ki",
    "1 Chronicles":"1Ch","2 Chronicles":"2Ch","Ezra":"Ezr","Nehemiah":"Neh",
    "Esther":"Est","Job":"Job","Psalms":"Psa","Proverbs":"Pro",
    "Ecclesiastes":"Ecc","Song of Solomon":"Son","Isaiah":"Isa",
    "Jeremiah":"Jer","Lamentations":"Lam","Ezekiel":"Eze","Daniel":"Dan",
    "Hosea":"Hos","Joel":"Joe","Amos":"Amo","Obadiah":"Oba","Jonah":"Jon",
    "Micah":"Mic","Nahum":"Nah","Habakkuk":"Hab","Zephaniah":"Zep",
    "Haggai":"Hag","Zechariah":"Zec","Malachi":"Mal","Matthew":"Mat",
    "Mark":"Mar","Luke":"Luk","John":"Joh","Acts":"Act","Romans":"Rom",
    "1 Corinthians":"1Co","2 Corinthians":"2Co","Galatians":"Gal",
    "Ephesians":"Eph","Philippians":"Phi","Colossians":"Col",
    "1 Thessalonians":"1Th","2 Thessalonians":"2Th","1 Timothy":"1Ti",
    "2 Timothy":"2Ti","Titus":"Tit","Philemon":"Phm","Hebrews":"Heb",
    "James":"Jam","1 Peter":"1Pe","2 Peter":"2Pe","1 John":"1Jo",
    "2 John":"2Jo","3 John":"3Jo","Jude":"Jud","Revelation":"Rev",
}

# ── Helpers ───────────────────────────────────────────────────────────────── #

def clean_text(text):
    """Strip Strong's concordance tags and any other XML tags from verse text."""
    # Remove Strong's tags like <S>5315</S> including the number
    text = re.sub(r"<S>\d+</S>", "", text)
    # Remove any remaining HTML/XML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Collapse extra spaces
    text = re.sub(r"  +", " ", text).strip()
    return text


def normalize(text):
    text = clean_text(text)   # strip tags first
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def get_or_create_version():
    v, _ = BibleVersion.objects.get_or_create(
        code="KJV",
        defaults={"name": "King James Version", "language": "English"},
    )
    return v


def create_books():
    books = {}
    for i, name in enumerate(BOOK_ORDER, 1):
        book, _ = Book.objects.get_or_create(
            name=name,
            defaults={
                "abbreviation": ABBREVIATIONS.get(name, name[:3]),
                "testament": "OT" if name in OT_BOOKS else "NT",
                "order": i,
            },
        )
        books[name] = book
    return books


def fetch_json(url, retries=3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 VerseFind/1.0"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2)
            else:
                raise e


def bulk_save(to_create):
    Verse.objects.bulk_create(to_create, ignore_conflicts=True)
    count = len(to_create)
    to_create.clear()
    return count


# ── Source 1: bolls.life ─────────────────────────────────────────────────── #

def load_from_bolls(version, books):
    """
    THE FIX: bolls.life requires a numeric book ID (1-66), NOT the book name.
    Old (broken): /get-chapter/KJV/Genesis/1/
    Fixed:        /get-text/KJV/1/1/          (1 = Genesis)
    """
    print("\n>>> Source 1: bolls.life")
    total = 0
    failed = []

    for book_name in BOOK_ORDER:
        book_id = BOLLS_BOOK_ID[book_name]          # <-- the fix
        num_chapters = CHAPTER_COUNTS[book_name]
        to_create = []
        book_ok = True

        for chapter in range(1, num_chapters + 1):
            url = f"https://bolls.life/get-text/KJV/{book_id}/{chapter}/"
            try:
                data = fetch_json(url)
                if not isinstance(data, list) or not data:
                    raise ValueError(f"Bad response: {str(data)[:80]}")
                for item in data:
                    text = item.get("text", "").strip()
                    verse_num = item.get("verse", 0)
                    if text and verse_num:
                        to_create.append(Verse(
                            version=version,
                            book=books[book_name],
                            chapter=chapter,
                            verse_number=verse_num,
                            text=text,
                            normalized_text=normalize(text),
                        ))
            except Exception as e:
                print(f"   ! {book_name} ch.{chapter} failed: {e}")
                book_ok = False
                failed.append(book_name)
                break

        if to_create:
            saved = bulk_save(to_create)
            total += saved
            status = "✓" if book_ok else "~"
            print(f"   {status} {book_name}: {saved} verses")
        else:
            print(f"   ✗ {book_name}: no data")
            if book_name not in failed:
                failed.append(book_name)

    print(f"\n   bolls.life total: {total} verses | failed books: {len(set(failed))}")
    return total, list(set(failed))


# ── Source 2: bible-api.com ──────────────────────────────────────────────── #

def load_from_bible_api(version, books, only_books=None):
    """
    bible-api.com — fallback for any books that failed on bolls.life.
    Covers all 66 books if needed.
    """
    print("\n>>> Source 2: bible-api.com")
    total = 0
    target = only_books if only_books else BOOK_ORDER

    for book_name in target:
        slug = BIBLE_API_SLUG.get(book_name, book_name.lower().replace(" ", ""))
        num_chapters = CHAPTER_COUNTS[book_name]
        to_create = []

        for chapter in range(1, num_chapters + 1):
            url = f"https://bible-api.com/{slug}{chapter}?translation=kjv"
            try:
                data = fetch_json(url)
                verses = data.get("verses", [])
                if not verses:
                    break
                for v in verses:
                    text = v.get("text", "").strip()
                    verse_num = v.get("verse", 0)
                    if text and verse_num:
                        to_create.append(Verse(
                            version=version,
                            book=books[book_name],
                            chapter=v.get("chapter", chapter),
                            verse_number=verse_num,
                            text=text,
                            normalized_text=normalize(text),
                        ))
            except Exception as e:
                print(f"   ! {book_name} ch.{chapter}: {e}")
                break

        if to_create:
            saved = bulk_save(to_create)
            total += saved
            print(f"   ✓ {book_name}: {saved} verses")
        else:
            print(f"   ✗ {book_name}: no data")

    print(f"\n   bible-api.com total: {total} verses")
    return total


# ── Source 3: GitHub raw JSON ────────────────────────────────────────────── #

def load_from_github(version, books):
    print("\n>>> Source 3: GitHub (aruljohn/Bible-kjv)")
    url = "https://raw.githubusercontent.com/aruljohn/Bible-kjv/master/Bible.json"
    try:
        data = fetch_json(url)
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return 0

    entries = data.get("books", [])
    if not entries:
        entries = [{"name": k, "chapters": v} for k, v in data.items()]

    total = 0
    to_create = []

    for entry in entries:
        book_name = entry.get("name", "")
        book = books.get(book_name)
        if not book:
            continue
        for ch_idx, chapter_verses in enumerate(entry.get("chapters", []), 1):
            for v_idx, text in enumerate(chapter_verses, 1):
                to_create.append(Verse(
                    version=version, book=book,
                    chapter=ch_idx, verse_number=v_idx,
                    text=clean_text(text), normalized_text=normalize(text),
                ))
                if len(to_create) >= 1000:
                    total += bulk_save(to_create)
                    print(f"   {total} verses...", end="\r")

    if to_create:
        total += bulk_save(to_create)

    print(f"\n   GitHub total: {total} verses")
    return total


# ── Source 4: Local file ─────────────────────────────────────────────────── #

def load_from_local_file(version, books):
    path = os.path.join(os.path.dirname(__file__), "kjv.json")
    if not os.path.exists(path):
        return 0

    print(f"\n>>> Source 4: Local file ({path})")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    entries = data.get("books", [])
    if not entries:
        entries = [{"name": k, "chapters": v} for k, v in data.items()]

    total = 0
    to_create = []

    for entry in entries:
        book_name = entry.get("name", "")
        book = books.get(book_name)
        if not book:
            continue
        for ch_idx, chapter_verses in enumerate(entry.get("chapters", []), 1):
            for v_idx, text in enumerate(chapter_verses, 1):
                to_create.append(Verse(
                    version=version, book=book,
                    chapter=ch_idx, verse_number=v_idx,
                    text=clean_text(text), normalized_text=normalize(text),
                ))
                if len(to_create) >= 1000:
                    total += bulk_save(to_create)

    if to_create:
        total += bulk_save(to_create)

    print(f"   Local file total: {total} verses")
    return total


# ── Main ──────────────────────────────────────────────────────────────────── #

def main():
    print("=" * 55)
    print("  VerseFind — KJV Bible Loader")
    print("=" * 55)

    existing = Verse.objects.filter(version__code="KJV").count()
    if existing > 30000:
        print(f"\n Already loaded ({existing} verses). Nothing to do.")
        print("   To reload, delete existing verses first:")
        print('   python manage.py shell -c "from bible.models import Verse; Verse.objects.filter(version__code=\'KJV\').delete()"')
        return

    version = get_or_create_version()
    books   = create_books()
    print(f"✓ Version and all 66 books ready\n")

    # 1. bolls.life (all 66 books with correct numeric IDs)
    total, failed = load_from_bolls(version, books)
    if total >= 30000:
        print(f"\n Complete! {total} verses loaded.")
        return

    # 2. bible-api.com for any failed books
    if failed:
        print(f"\n⚠  Retrying {len(failed)} failed books via bible-api.com...")
        total += load_from_bible_api(version, books, only_books=failed)
    if total >= 30000:
        print(f"\n Complete! {total} verses loaded.")
        return

    # 3. GitHub JSON (whole Bible in one request)
    print(f"\n⚠  Only {total} verses — trying GitHub...")
    total += load_from_github(version, books)
    if total >= 30000:
        print(f"\n Complete! {total} verses loaded.")
        return

    # 4. Local file
    total += load_from_local_file(version, books)

    final = Verse.objects.filter(version__code="KJV").count()
    if final >= 30000:
        print(f"\n Complete! {final} verses loaded.")
    elif final > 0:
        print(f"\n⚠  Partial load: {final} verses.")
        print("   Download Bible.json from https://github.com/aruljohn/Bible-kjv")
        print("   Save as scripts/kjv.json and re-run.")
    else:
        print("\n No verses loaded. All sources failed.")
        print("   Download Bible.json from https://github.com/aruljohn/Bible-kjv")
        print("   Save as scripts/kjv.json and re-run.")


if __name__ == "__main__":
    main()