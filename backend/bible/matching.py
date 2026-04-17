"""
VerseFind Matching Engine
=========================
Phase 1 (MVP):  rapidfuzz-based fuzzy + keyword matching
Phase 2 (TODO): pgvector semantic search with embeddings

Strategy:
  1. Normalize input (lowercase, strip punctuation, collapse whitespace)
  2. Keyword pre-filter — pull candidate verses from DB where any significant
     word appears in normalized_text (fast SQL LIKE / full-text search)
  3. Score candidates with rapidfuzz partial_ratio (handles partial quotes)
  4. Return top match + confidence
"""

import re
import unicodedata
from typing import Optional

from rapidfuzz import fuzz, process

from bible.models import Verse, BibleVersion


# --------------------------------------------------------------------------- #
#  Text normalisation
# --------------------------------------------------------------------------- #

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "of", "to", "for",
    "with", "that", "this", "it", "is", "was", "be", "as", "at",
    "by", "his", "her", "their", "he", "she", "they", "we", "i",
    "ye", "thou", "thee", "thy", "thine", "shall", "shalt", "hath",
    "doth", "unto", "upon", "which", "who", "whom", "not",
}


def normalize(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace, remove stopwords."""
    text = text.lower()
    # Remove punctuation & special chars (keep spaces)
    text = unicodedata.normalize("NFD", text)
    text = re.sub(r"[^\w\s]", " ", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_keywords(normalized: str, min_len: int = 4) -> list[str]:
    """Return significant words (non-stopwords, length >= min_len)."""
    words = normalized.split()
    return [w for w in words if w not in STOPWORDS and len(w) >= min_len]


# --------------------------------------------------------------------------- #
#  Candidate fetching
# --------------------------------------------------------------------------- #

def fetch_candidates(keywords: list[str], version_code: str = "KJV", limit: int = 200):
    """
    Pull candidate verses from DB where any keyword appears.
    Uses Django ORM — works with any DB backend.
    Falls back to full scan if no keywords extracted (short input).
    """
    qs = Verse.objects.select_related("book", "version").filter(
        version__code=version_code
    )

    if keywords:
        from django.db.models import Q
        query = Q()
        for kw in keywords[:6]:  # cap at 6 keywords to keep query sane
            query |= Q(normalized_text__icontains=kw)
        qs = qs.filter(query)
    
    return list(qs[:limit])


# --------------------------------------------------------------------------- #
#  Scoring
# --------------------------------------------------------------------------- #

def score_candidates(normalized_input: str, candidates: list) -> list[dict]:
    """
    Score each candidate with rapidfuzz.
    Uses partial_ratio to handle incomplete quotes.
    Returns list of dicts sorted by score desc.
    """
    if not candidates:
        return []

    # Build (text, index) pairs for rapidfuzz
    choices = {i: c.normalized_text for i, c in enumerate(candidates)}

    results = []
    for idx, verse in enumerate(candidates):
        score = fuzz.partial_ratio(normalized_input, verse.normalized_text)
        # Bonus: token sort ratio (handles reordered words)
        token_score = fuzz.token_sort_ratio(normalized_input, verse.normalized_text)
        final_score = max(score, token_score)
        results.append({"verse": verse, "score": final_score})

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


# --------------------------------------------------------------------------- #
#  Public API
# --------------------------------------------------------------------------- #

def find_verse(
    raw_input: str,
    version_code: str = "KJV",
    top_n: int = 5,
    min_confidence: int = 45,
) -> dict:
    """
    Main entry point.

    Returns:
        {
            "query": original input,
            "results": [
                {
                    "verse": Verse instance,
                    "score": 0-100,
                    "reference": "John 3:16",
                    "text": "...",
                    "book": "John",
                    "chapter": 3,
                    "verse_number": 16,
                    "version": "KJV",
                }
            ],
            "found": bool,
            "top_match": first result or None,
        }
    """
    normalized_input = normalize(raw_input)
    keywords = extract_keywords(normalized_input)

    candidates = fetch_candidates(keywords, version_code=version_code)

    # If very few candidates (keyword miss), widen to full scan
    if len(candidates) < 10:
        candidates = fetch_candidates([], version_code=version_code, limit=500)

    scored = score_candidates(normalized_input, candidates)

    results = []
    for item in scored[:top_n]:
        if item["score"] < min_confidence:
            break
        verse = item["verse"]
        results.append({
            "score": item["score"],
            "reference": verse.reference,
            "text": verse.text,
            "book": verse.book.name,
            "chapter": verse.chapter,
            "verse_number": verse.verse_number,
            "version": verse.version.code,
            "testament": verse.book.testament,
        })

    return {
        "query": raw_input,
        "normalized": normalized_input,
        "results": results,
        "found": len(results) > 0,
        "top_match": results[0] if results else None,
    }


def get_context_verses(book_name: str, chapter: int, verse_number: int, version_code: str = "KJV", window: int = 3):
    """Return surrounding verses for context (±window verses)."""
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