"""
VerseFind Matching Engine — Semantic + Phonetic + Indexed
==========================================================

Three layers working together:

  LAYER 1 — Semantic Expansion
    Maps user words to synonyms and archaic equivalents before searching.
    "over" → also searches "against"  (Micah 7:8 now matches)
    "thy"  → also searches "your"     (archaic → modern)
    "fear" → also searches "afraid"   (synonym)

  LAYER 2 — Phonetic Matching (Soundex)
    Indexes every verse word by its Soundex code at load time.
    "sheperd" → S163 → finds "shepherd" (S163)
    Handles speech recognition errors and spelling mistakes.

  LAYER 3 — Hybrid Scoring
    partial_ratio    × 0.55  — handles partial quotes
    semantic_score   × 0.30  — synonym/stem overlap
    token_sort_ratio × 0.15  — handles word order

  PLUS — Pre-built phonetic index on the Verse queryset for
    instant lookup without scanning every row.
"""

import re
import unicodedata
from django.db.models import Q
from rapidfuzz import fuzz
from bible.models import Verse


# ── Semantic map: user word → list of equivalent words to also search ─────── #

SEMANTIC_MAP = {
    # Archaic KJV → modern equivalents
    "thy": ["your"], "thee": ["you"], "thou": ["you", "ye"],
    "thine": ["your"], "ye": ["you", "thou"],
    "hast": ["have"], "hath": ["has"], "doth": ["does"],
    "saith": ["says", "said"], "art": ["are"],
    "wilt": ["will"], "canst": ["can"], "wouldst": ["would"],
    "liveth": ["lives", "live"], "cometh": ["comes", "come"],
    "goeth": ["goes", "go"], "knoweth": ["knows", "know"],
    "giveth": ["gives", "give"], "taketh": ["takes", "take"],
    "speaketh": ["speaks", "speak"], "dwelleth": ["dwells", "dwell"],
    "walketh": ["walks", "walk"], "standeth": ["stands", "stand"],
    "mine": ["my"], "unto": ["to"], "upon": ["on"],
    "yea": ["yes", "indeed"], "nay": ["no"],
    "lo": ["behold", "look", "see"], "behold": ["look", "see", "lo"],
    "verily": ["truly", "indeed"],
    # Synonyms
    "against": ["over", "upon"],
    "over": ["against", "upon"],
    "enemy": ["foe", "adversary", "enemies"],
    "enemies": ["foe", "adversary", "enemy"],
    "foe": ["enemy", "adversary"],
    "rejoice": ["glad", "joy", "happy", "celebrate"],
    "glad": ["rejoice", "happy", "joyful"],
    "faith": ["believe", "trust", "belief"],
    "believe": ["faith", "trust"],
    "trust": ["faith", "believe", "rely"],
    "righteous": ["just", "holy", "upright"],
    "just": ["righteous", "fair", "upright"],
    "upright": ["righteous", "just", "straight"],
    "soul": ["spirit", "heart", "life"],
    "heart": ["soul", "spirit", "mind"],
    "spirit": ["soul", "heart"],
    "light": ["lamp", "shine", "illuminate"],
    "lamp": ["light", "candle"],
    "darkness": ["dark", "night", "shadow"],
    "shepherd": ["pastor", "guide", "keeper"],
    "arise": ["rise", "stand", "get up"],
    "rise": ["arise", "stand"],
    "fall": ["fell", "fallen", "stumble"],
    "fell": ["fall", "fallen"],
    "blessed": ["happy", "blest", "fortunate"],
    "wicked": ["evil", "sinful", "ungodly"],
    "evil": ["wicked", "sin", "bad"],
    "fear": ["afraid", "terror", "reverence", "dread"],
    "afraid": ["fear", "terror", "dread"],
    "saved": ["delivered", "rescued", "redeemed"],
    "delivered": ["saved", "rescued"],
    "strength": ["power", "might", "force"],
    "power": ["strength", "might"],
    "mighty": ["strong", "powerful"],
    "grace": ["mercy", "favor", "kindness"],
    "mercy": ["grace", "compassion", "kindness"],
    "compassion": ["mercy", "pity"],
    "peace": ["rest", "calm", "shalom"],
    "rest": ["peace", "calm"],
    "word": ["scripture", "commandment"],
    "lord": ["god", "master"],
    "god": ["lord", "father", "almighty"],
    "father": ["god", "lord"],
    "anger": ["wrath", "fury", "rage"],
    "wrath": ["anger", "fury"],
    "fury": ["anger", "wrath"],
    "praise": ["worship", "glorify", "honor"],
    "worship": ["praise", "adore"],
    "pray": ["prayer", "intercede", "petition"],
    "love": ["charity", "affection"],
    "charity": ["love"],
    "hope": ["trust", "expectation"],
    "joy": ["rejoice", "glad", "happiness"],
    "happiness": ["joy", "glad", "blessed"],
    "sin": ["evil", "transgression", "iniquity"],
    "transgression": ["sin", "iniquity"],
    "iniquity": ["sin", "transgression"],
    "heal": ["cure", "restore"],
    "restore": ["heal", "renew"],
    "forgive": ["pardon", "remit"],
    "pardon": ["forgive", "remit"],
    "holy": ["sacred", "righteous", "pure"],
    "sacred": ["holy"],
    "pure": ["holy", "clean"],
    "clean": ["pure"],
}


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
    "even","more","man","upon","thus","therefore",
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


# ── Soft stemming ─────────────────────────────────────────────────────────── #

def stem(word: str) -> str:
    """Strip common suffixes to get approximate base form."""
    suffixes = ["ieth", "eth", "ing", "ness", "tion", "ation",
                "ed", "est", "ly", "ful", "less"]
    for suffix in suffixes:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[:-len(suffix)]
    return word


# ── Phonetic index (Soundex) ──────────────────────────────────────────────── #

def soundex(word: str) -> str:
    """
    Soundex algorithm — maps similar-sounding words to the same code.
    'shepherd' and 'sheperd' both → S163
    'righteousness' and 'rightousness' both → R232
    """
    if not word:
        return ""
    word = word.upper()
    codes = {
        'B':'1','F':'1','P':'1','V':'1',
        'C':'2','G':'2','J':'2','K':'2','Q':'2','S':'2','X':'2','Z':'2',
        'D':'3','T':'3',
        'L':'4',
        'M':'5','N':'5',
        'R':'6',
    }
    result = word[0]
    prev = codes.get(word[0], '0')
    for char in word[1:]:
        code = codes.get(char, '0')
        if code != '0' and code != prev:
            result += code
        prev = code
    return (result + '000')[:4]


# In-memory phonetic index: soundex_code → list of actual words in the Bible
# Built once on first use, reused for all subsequent searches
_phonetic_index: dict[str, set[str]] = {}
_phonetic_index_built = False

def build_phonetic_index() -> None:
    """
    Build a soundex → {words} index from all normalized verse text.
    Called once. After this, phonetic_expand() is instant.
    """
    global _phonetic_index, _phonetic_index_built
    if _phonetic_index_built:
        return

    print("Building phonetic index...")
    # Sample distinct words from normalized verse text
    # Use values_list for efficiency — don't load full Verse objects
    from django.db.models.functions import Length
    texts = Verse.objects.filter(
        version__code="KJV"
    ).values_list("normalized_text", flat=True)

    for text in texts.iterator(chunk_size=1000):
        for word in text.split():
            if len(word) >= 3:
                code = soundex(word)
                if code not in _phonetic_index:
                    _phonetic_index[code] = set()
                _phonetic_index[code].add(word)

    _phonetic_index_built = True
    print(f"Phonetic index built: {len(_phonetic_index)} codes")


def phonetic_expand(word: str) -> list[str]:
    """
    Return all Bible words that sound like `word`.
    e.g. 'sheperd' → ['shepherd']
         'enemie'  → ['enemy']
    """
    if not _phonetic_index_built:
        build_phonetic_index()
    code = soundex(word)
    return list(_phonetic_index.get(code, set()))


# ── Semantic + phonetic query expansion ──────────────────────────────────── #

def expand_terms(normalized_input: str) -> tuple[list[str], list[str]]:
    """
    Returns:
      original_keywords — content words from input (for scoring)
      search_terms      — original + synonyms + stems + phonetic variants
                          (for DB query — casts a wider net)
    """
    words = normalized_input.split()
    original_kw = [w for w in words if w not in STOPWORDS and len(w) >= 3]

    search_set = set(original_kw)

    for word in original_kw:
        stemmed = stem(word)
        search_set.add(stemmed)

        # Semantic synonyms
        if word in SEMANTIC_MAP:
            search_set.update(SEMANTIC_MAP[word])
        if stemmed in SEMANTIC_MAP:
            search_set.update(SEMANTIC_MAP[stemmed])

        # Phonetic variants (catches speech errors)
        phonetic_matches = phonetic_expand(word)
        search_set.update(phonetic_matches[:5])  # cap at 5 to avoid noise

    return original_kw, list(search_set)


# ── Candidate fetching ────────────────────────────────────────────────────── #

def fetch_candidates(normalized_input: str, version_code: str = "KJV",
                     limit: int = 200) -> list:
    """
    For long inputs (>6 words): phrase search first, then keyword fallback.
    For short inputs (<=6 words): semantic keyword search with expanded terms.
    """
    qs = Verse.objects.select_related("book", "version").filter(
        version__code=version_code
    )
    words = normalized_input.split()
    original_kw, search_terms = expand_terms(normalized_input)

    # ── LONG input: phrase search ──────────────────────────────────────── #
    if len(words) > 6:
        # 3-word and 4-word consecutive phrases
        ngrams = []
        for n in (4, 3):
            for i in range(len(words) - n + 1):
                ngrams.append(" ".join(words[i:i + n]))

        if ngrams:
            q = Q()
            for ng in ngrams[:8]:
                q |= Q(normalized_text__icontains=ng)
            results = list(qs.filter(q)[:limit])
            if len(results) >= 3:
                return results

        # 2-word phrases
        bigrams = [" ".join(words[i:i+2]) for i in range(len(words)-1)]
        if bigrams:
            q = Q()
            for bg in bigrams[:10]:
                q |= Q(normalized_text__icontains=bg)
            results = list(qs.filter(q)[:limit])
            if len(results) >= 3:
                return results

    # ── ALL inputs: semantic keyword search ───────────────────────────── #
    # AND: verse must contain all original keywords (or their synonyms)
    if original_kw:
        # Build an AND query where each keyword can match itself OR a synonym
        q_and = Q()
        for kw in original_kw[:6]:
            stemmed = stem(kw)
            syns = set(SEMANTIC_MAP.get(kw, []) + SEMANTIC_MAP.get(stemmed, []))
            syns.add(kw)
            syns.add(stemmed)
            kw_q = Q()
            for term in list(syns)[:5]:
                kw_q |= Q(normalized_text__icontains=term)
            q_and &= kw_q

        results = list(qs.filter(q_and)[:limit])
        if results:
            return results

    # OR fallback: any expanded term present
    if search_terms:
        q_or = Q()
        for term in search_terms[:10]:
            q_or |= Q(normalized_text__icontains=term)
        results = list(qs.filter(q_or)[:limit])
        if results:
            return results

    return []


# ── Semantic scoring ──────────────────────────────────────────────────────── #

def semantic_score(original_kw: list[str], verse_normalized: str) -> float:
    """
    Score how well original keywords are represented in the verse,
    giving full credit for direct matches and partial credit for synonyms.
    """
    if not original_kw:
        return 0.0

    verse_words = set(verse_normalized.split())
    score = 0.0

    for kw in original_kw:
        stemmed = stem(kw)
        # Direct match
        if kw in verse_words or stemmed in verse_words:
            score += 1.0
            continue
        # Phonetic match
        phonetic = set(phonetic_expand(kw))
        if phonetic & verse_words:
            score += 0.8
            continue
        # Synonym match
        syns = set(SEMANTIC_MAP.get(kw, []) + SEMANTIC_MAP.get(stemmed, []))
        if syns & verse_words:
            score += 0.6
            continue

    return score / len(original_kw)


# ── Candidate scoring ─────────────────────────────────────────────────────── #

def score_candidates(normalized_input: str, candidates: list) -> list[dict]:
    """
    Hybrid scoring:
      partial_ratio    × 0.55  — handles partial quotes and subsequences
      semantic_score   × 0.30  — synonym/stem/phonetic overlap
      token_sort_ratio × 0.15  — handles word order differences

    Final score 0-100.
    """
    if not candidates:
        return []

    original_kw, _ = expand_terms(normalized_input)
    results = []

    for verse in candidates:
        vn = verse.normalized_text
        partial    = fuzz.partial_ratio(normalized_input, vn)
        token_sort = fuzz.token_sort_ratio(normalized_input, vn)
        sem        = semantic_score(original_kw, vn) * 100

        final = (partial * 0.55) + (sem * 0.30) + (token_sort * 0.15)

        results.append({
            "verse":    verse,
            "score":    round(final),
            "semantic": round(sem),
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


# ── Public API ────────────────────────────────────────────────────────────── #

def find_verse(
    raw_input: str,
    version_code: str = "KJV",
    top_n: int = 5,
    min_confidence: int = 52,
) -> dict:
    """
    Main entry point. Returns best matching verses.

    A result qualifies if:
      score >= min_confidence (52)
      semantic_score >= 50%  (at least half the input words meaningfully
                               appear in the verse, counting synonyms)
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
    for item in scored[:top_n * 2]:
        if item["score"] < min_confidence:
            break
        if item["semantic"] < 50:
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
        "query": raw_input, "normalized": normalized_input,
        "results": [], "found": False, "top_match": None,
        "message": message,
    }


def get_context_verses(book_name: str, chapter: int, verse_number: int,
                       version_code: str = "KJV", window: int = 3) -> list:
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