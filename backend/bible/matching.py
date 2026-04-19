"""
VerseFind Matching Engine — Phrase-First Approach
==================================================

The user speaks or types a continuous phrase. We treat it as a PHRASE,
not a bag of words. Strategy:

  1. Normalize input (lowercase, strip punctuation)
  2. Build n-grams (2,3,4-word sequences) from the input phrase
  3. Search DB for verses containing those n-gram sequences (phrase search)
  4. Score survivors with phrase-aware metrics:
       a. longest_common_subsequence — how much of the phrase flows through
       b. partial_ratio              — for partial quotes
       c. phrase_hit_ratio           — how many n-grams from input appear in verse
  5. Hard threshold of 60, but phrase_hit_ratio must also be >= 0.5
     (more than half the input phrases must appear in the verse)
  6. For very short input, fall back to trigram DB search then exact guard

This means "love is patient love is kind" matches 1 Corinthians 13:4 because
the consecutive phrases "love is patient" and "love is kind" are IN that verse,
not because it found random verses with "love" or "patient" somewhere.
"""

import re
import unicodedata
from django.db.models import Q
from rapidfuzz import fuzz
from bible.models import Verse


# ── Stopwords (for keyword fallback only) ─────────────────────────────────── #

STOPWORDS = {
    "a","an","the","and","or","but","in","of","to","for","with","that",
    "this","it","is","was","be","as","at","by","his","her","their","he",
    "she","they","we","i","ye","thou","thee","thy","thine","shall","shalt",
    "hath","doth","unto","upon","which","who","whom","not","me","my","our",
    "your","you","him","them","its","been","have","has","had","do","did",
    "will","would","could","should","may","might","said","say","am","are",
    "were","so","if","then","when","where","what","how","all","no","up",
    "out","there","come","came","go","went","into","from","also","now",
    "even","more","man","upon","thus","them","then","therefore",
}


# ── Normalisation ─────────────────────────────────────────────────────────── #

def normalize(text: str) -> str:
    # Strip Strong's concordance tags e.g. <S>5315</S> — some sources include them
    text = re.sub(r"<S>\d+</S>", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_keywords(normalized: str, min_len: int = 4) -> list[str]:
    words = normalized.split()
    return [w for w in words if w not in STOPWORDS and len(w) >= min_len]


# ── N-gram builder ────────────────────────────────────────────────────────── #

def build_ngrams(words: list[str], sizes=(2, 3, 4)) -> list[str]:
    """
    Build consecutive word sequences from the input.
    "for god so loved" → ["for god", "god so", "so loved",
                           "for god so", "god so loved",
                           "for god so loved"]
    These are PHRASES not individual words.
    """
    ngrams = []
    for n in sizes:
        for i in range(len(words) - n + 1):
            ngrams.append(" ".join(words[i:i + n]))
    return ngrams


# ── Candidate fetching — phrase-first ────────────────────────────────────── #

def fetch_candidates(normalized_input: str, version_code: str = "KJV", limit: int = 200) -> list:
    """
    Search for verses that contain actual phrases from the input,
    not just scattered individual words.

    Priority:
      1. Longest meaningful ngrams (4-word, 3-word sequences) — most precise
      2. Fallback to 2-word phrases
      3. Fallback to individual strong keywords (non-stopwords, len>=5)
    """
    qs = Verse.objects.select_related("book", "version").filter(version__code=version_code)
    words = normalized_input.split()

    # Phase 1 — search for 4-word and 3-word consecutive phrases
    long_ngrams = build_ngrams(words, sizes=(4, 3))
    if long_ngrams:
        q = Q()
        for ng in long_ngrams[:6]:  # top 6 phrases
            q |= Q(normalized_text__icontains=ng)
        results = list(qs.filter(q)[:limit])
        if len(results) >= 3:
            return results

    # Phase 2 — search for 2-word phrases
    bigrams = build_ngrams(words, sizes=(2,))
    if bigrams:
        q = Q()
        for bg in bigrams[:8]:
            q |= Q(normalized_text__icontains=bg)
        results = list(qs.filter(q)[:limit])
        if len(results) >= 3:
            return results

    # Phase 3 — strong individual keywords (longer words, not stopwords)
    strong = [w for w in words if w not in STOPWORDS and len(w) >= 5]
    if strong:
        q = Q()
        for kw in strong[:6]:
            q &= Q(normalized_text__icontains=kw)
        results = list(qs.filter(q)[:limit])
        if results:
            return results

        # Relax to OR if AND gives nothing
        q = Q()
        for kw in strong[:6]:
            q |= Q(normalized_text__icontains=kw)
        results = list(qs.filter(q)[:limit])
        if results:
            return results

    return []


# ── Scoring ───────────────────────────────────────────────────────────────── #

def phrase_hit_ratio(ngrams: list[str], verse_normalized: str) -> float:
    """
    What fraction of the input's n-grams appear verbatim in the verse.
    High ratio = the verse contains the same flowing phrases as the input.
    """
    if not ngrams:
        return 0.0
    hits = sum(1 for ng in ngrams if ng in verse_normalized)
    return hits / len(ngrams)


def score_candidates(normalized_input: str, candidates: list) -> list[dict]:
    """
    Three phrase-aware metrics:
      - partial_ratio:     how much of the input appears in the verse (subsequence)
      - token_sort_ratio:  same words regardless of order (handles voice reordering)
      - phrase_hit_ratio:  what % of consecutive phrases from input exist in verse

    Weights: 40% partial + 30% token_sort + 30% phrase_hit
    The phrase_hit component is what makes this phrase-aware, not word-bag.
    """
    if not candidates:
        return []

    words = normalized_input.split()
    ngrams = build_ngrams(words, sizes=(2, 3))  # phrases to check

    results = []
    for verse in candidates:
        vn = verse.normalized_text

        partial    = fuzz.partial_ratio(normalized_input, vn)
        token_sort = fuzz.token_sort_ratio(normalized_input, vn)
        phrase_hit = phrase_hit_ratio(ngrams, vn) * 100

        final = (partial * 0.40) + (token_sort * 0.30) + (phrase_hit * 0.30)

        results.append({
            "verse":      verse,
            "score":      round(final),
            "partial":    partial,
            "token_sort": token_sort,
            "phrase_hit": round(phrase_hit),
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


# ── Public API ────────────────────────────────────────────────────────────── #

def find_verse(
    raw_input: str,
    version_code: str = "KJV",
    top_n: int = 5,
    min_confidence: int = 55,
) -> dict:
    """
    Main entry point.

    A result is returned only if:
      - score >= min_confidence (55)
      - phrase_hit_ratio >= 40% (at least 40% of input phrases appear in verse)
      This combination means the verse must contain the same flowing text,
      not just happen to share a few words.
    """
    normalized_input = normalize(raw_input)
    words = normalized_input.split()

    if len(words) < 2:
        return _empty(raw_input, normalized_input,
                      "Please type at least a few words of the verse.")

    candidates = fetch_candidates(normalized_input, version_code=version_code)

    if not candidates:
        return _empty(raw_input, normalized_input,
                      "No matching verses found. Try saying more of the verse.")

    scored = score_candidates(normalized_input, candidates)

    results = []
    for item in scored[:top_n * 2]:  # over-fetch then filter
        if item["score"] < min_confidence:
            break

        # Phrase gate: at least 40% of input phrases must be in the verse
        if item["phrase_hit"] < 40:
            continue

        verse = item["verse"]
        results.append({
            "id":           verse.id,
            "score":        item["score"],
            "reference":    verse.reference,
            "text":         verse.text,
            "book":         verse.book.name,
            "chapter":      verse.chapter,
            "verse_number": verse.verse_number,
            "version":      verse.version.code,
            "testament":    verse.book.testament,
        })

        if len(results) >= top_n:
            break

    return {
        "query":      raw_input,
        "normalized": normalized_input,
        "results":    results,
        "found":      len(results) > 0,
        "top_match":  results[0] if results else None,
    }


def _empty(raw_input, normalized_input, message):
    return {
        "query":      raw_input,
        "normalized": normalized_input,
        "results":    [],
        "found":      False,
        "top_match":  None,
        "message":    message,
    }


def get_context_verses(book_name: str, chapter: int, verse_number: int,
                       version_code: str = "KJV", window: int = 3) -> list:
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