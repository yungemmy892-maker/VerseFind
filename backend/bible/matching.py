"""
VerseFind Matching Engine (Improved)
===================================

Enhancements:
- Better candidate retrieval (less strict)
- Stronger partial quote handling
- Improved scoring weights
- Safer fallback logic
"""

import re
import unicodedata
from django.db.models import Q
from rapidfuzz import fuzz
from bible.models import Verse


# ── Stopwords ─────────────────────────────────────────────────────────────── #

STOPWORDS = {
    "a","an","the","and","or","but","in","of","to","for","with","that",
    "this","it","is","was","be","as","at","by","his","her","their","he",
    "she","they","we","i","ye","thou","thee","thy","thine","shall","shalt",
    "hath","doth","unto","upon","which","who","whom","not","me","my","our",
    "your","you","him","them","its","been","have","has","had","do","did",
    "will","would","could","should","may","might","said","say","am","are",
    "were","so","if","then","when","where","what","how","all","no","up",
    "out","there","come","came","go","went","into","from","also","now",
    "even","more","man","upon","thus","therefore","against","mine","over",
}


# ── Normalisation ─────────────────────────────────────────────────────────── #

def normalize(text: str) -> str:
    text = re.sub(r"<S>\d+</S>", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_keywords(normalized: str, min_len: int = 3) -> list[str]:
    return [w for w in normalized.split() if w not in STOPWORDS and len(w) >= min_len]


def build_ngrams(words: list[str], sizes=(2, 3, 4)) -> list[str]:
    ngrams = []
    for n in sizes:
        for i in range(len(words) - n + 1):
            ngrams.append(" ".join(words[i:i + n]))
    return ngrams


# ── Candidate fetching ────────────────────────────────────────────────────── #

def fetch_candidates(normalized_input: str, version_code="KJV", limit=300):
    qs = Verse.objects.select_related("book", "version").filter(
        version__code=version_code
    )

    words = normalized_input.split()
    keywords = extract_keywords(normalized_input)

    # ── LONG INPUT: phrase-first but less strict ─────────────────────────── #
    if len(words) > 6:
        ngrams = build_ngrams(words, sizes=(4, 3, 2))

        if ngrams:
            q = Q()
            for ng in ngrams[:15]:   # 🔥 increased coverage
                q |= Q(normalized_text__icontains=ng)

            results = list(qs.filter(q)[:limit])

            if results:  # ✅ FIX: accept any result
                return results

    # ── KEYWORD AND ─────────────────────────────────────────────────────── #
    if keywords:
        q_and = Q()
        for kw in keywords[:8]:
            q_and &= Q(normalized_text__icontains=kw)

        results = list(qs.filter(q_and)[:limit])
        if results:
            return results

    # ── KEYWORD OR (fallback) ───────────────────────────────────────────── #
    if keywords:
        q_or = Q()
        for kw in keywords[:10]:
            q_or |= Q(normalized_text__icontains=kw)

        results = list(qs.filter(q_or)[:limit])
        if results:
            return results

    return []


# ── Scoring ───────────────────────────────────────────────────────────────── #

def keyword_coverage(keywords, verse_text):
    if not keywords:
        return 0
    return sum(1 for k in keywords if k in verse_text) / len(keywords)


def phrase_hit_ratio(ngrams, verse_text):
    if not ngrams:
        return 0
    return sum(1 for ng in ngrams if ng in verse_text) / len(ngrams)


def score_candidates(normalized_input, candidates, is_partial):
    words = normalized_input.split()
    keywords = extract_keywords(normalized_input)
    is_short = len(words) <= 6
    ngrams = build_ngrams(words, sizes=(2, 3)) if not is_short else []

    results = []

    for verse in candidates:
        vn = verse.normalized_text

        partial = fuzz.partial_ratio(normalized_input, vn)
        token   = fuzz.token_sort_ratio(normalized_input, vn)

        if is_short:
            coverage = keyword_coverage(keywords, vn) * 100
            final = (partial * 0.45) + (token * 0.30) + (coverage * 0.25)

        else:
            coverage = phrase_hit_ratio(ngrams, vn) * 100

            # 🔥 Improved partial handling
            if is_partial:
                final = (partial * 0.65) + (token * 0.20) + (coverage * 0.15)
            else:
                final = (partial * 0.50) + (token * 0.25) + (coverage * 0.25)

        results.append({
            "verse": verse,
            "score": round(final),
            "coverage": round(coverage),
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


# ── Public API ────────────────────────────────────────────────────────────── #

def find_verse(raw_input, version_code="KJV", top_n=5, min_confidence=40):
    normalized_input = normalize(raw_input)
    words = normalized_input.split()

    is_partial = not raw_input.rstrip().endswith(('.', '!', '?', '"', "'"))

    if len(words) < 2:
        return _empty(raw_input, normalized_input,
                      "Type a few more words.")

    candidates = fetch_candidates(normalized_input, version_code)

    if not candidates:
        return _empty(raw_input, normalized_input,
                      "No matching verses found. Try more words.")

    scored = score_candidates(normalized_input, candidates, is_partial)

    is_short = len(words) <= 6

    # 🔥 More forgiving coverage gate
    if is_short:
        coverage_gate = 35 if is_partial else 45
    else:
        coverage_gate = 10 if is_partial else 30

    results = []

    for item in scored[:top_n * 3]:
        if item["score"] < min_confidence:
            continue
        if item["coverage"] < coverage_gate:
            continue

        v = item["verse"]

        results.append({
            "id": v.id,
            "score": item["score"],
            "reference": v.reference,
            "text": v.text,
            "book": v.book.name,
            "chapter": v.chapter,
            "verse_number": v.verse_number,
            "version": v.version.code,
            "testament": v.book.testament,
        })

        if len(results) >= top_n:
            break

    return {
        "query": raw_input,
        "normalized": normalized_input,
        "results": results,
        "found": bool(results),
        "top_match": results[0] if results else None,
    }


def _empty(raw_input, normalized_input, message):
    return {
        "query": raw_input,
        "normalized": normalized_input,
        "results": [],
        "found": False,
        "top_match": None,
        "message": message,
    }


def get_context_verses(book_name, chapter, verse_number,
                       version_code="KJV", window=3):
    try:
        qs = Verse.objects.filter(
            version__code=version_code,
            book__name=book_name,
            chapter=chapter,
            verse_number__in=range(
                max(1, verse_number - window),
                verse_number + window + 1,
            ),
        ).select_related("book", "version").order_by("verse_number")

        return list(qs)

    except Exception:
        return []