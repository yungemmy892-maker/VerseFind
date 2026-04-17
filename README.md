# VerseFind 📖

**Shazam for Bible verses** — identify any Bible verse instantly by speaking or typing a fragment.

---

## How it works

1. User speaks or types part of a verse (e.g. "the Lord is my shepherd")
2. Voice is transcribed via Whisper (or Web Speech API fallback)
3. Django backend normalises text and runs fuzzy matching (rapidfuzz) against the Bible database
4. Best match returned with confidence score, reference, and context

---

## Project structure

```
versefind/
├── backend/          Django + DRF API
│   ├── versefind/    project settings & URLs
│   ├── bible/        models (Verse, Book, BibleVersion) + matching engine
│   ├── api/          REST endpoints
│   └── scripts/      KJV data loader
└── frontend/         React app
    └── src/
        ├── pages/    IdentifyScreen, ResultScreen, LibraryScreen, ChapterScreen
        ├── hooks/    useVoiceRecorder
        └── services/ api.js (all fetch calls)
```

---

## Setup — Backend

### 1. Prerequisites
- Python 3.11+
- PostgreSQL 14+

### 2. Create database
```bash
psql -U postgres
CREATE DATABASE versefind;
\q
```

### 3. Install dependencies
```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Configure environment
```bash
cp .env.example .env
# Edit .env — fill in DB_PASSWORD and optionally OPENAI_API_KEY
```

Generate a secret key:
```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

### 5. Run migrations
```bash
python manage.py migrate
```

### 6. Load KJV Bible data
```bash
python scripts/load_kjv.py
```
This downloads the public-domain KJV JSON (~800KB) and loads all 31,102 verses.
Takes ~30 seconds. Run once.

> **Offline alternative:** Download `Bible.json` from  
> https://github.com/aruljohn/Bible-kjv  
> Place it at `scripts/kjv.json` and run the script again.

### 7. Start Django
```bash
python manage.py runserver
```
API is live at http://localhost:8000/api/

---

## Setup — Frontend

### 1. Prerequisites
- Node.js 18+

### 2. Install & run
```bash
cd frontend
npm install
npm start
```
App is live at http://localhost:3000

---

## Voice transcription options

### Option A — OpenAI Whisper API (recommended, easiest)
```env
OPENAI_API_KEY=sk-...
USE_LOCAL_WHISPER=False
```
Costs ~$0.006 per minute of audio. A typical verse query is under 5 seconds.

### Option B — Local Whisper (free, runs on your machine)
```bash
pip install openai-whisper
# Also requires: pip install torch  (large download ~2GB)
```
```env
USE_LOCAL_WHISPER=True
```
Use `base` model for speed, `medium` for better accuracy with Nigerian English.

### Option C — No transcription (text-only MVP)
Leave both options unconfigured. Voice button will show a warning, text input works fully.

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/identify/` | Match text to a verse |
| POST | `/api/transcribe/` | Audio file → text |
| GET | `/api/verse/` | Single verse + context |
| GET | `/api/chapter/` | Full chapter |
| GET | `/api/saved/` | List saved verses |
| POST | `/api/saved/` | Save a verse |
| DELETE | `/api/saved/<id>/` | Remove saved verse |
| GET | `/api/versions/` | Available Bible versions |

### Example: Identify a verse
```bash
curl -X POST http://localhost:8000/api/identify/ \
  -H "Content-Type: application/json" \
  -d '{"text": "the lord is my shepherd i shall not want", "version": "KJV"}'
```

Response:
```json
{
  "query": "the lord is my shepherd i shall not want",
  "found": true,
  "top_match": {
    "score": 97,
    "reference": "Psalms 23:1",
    "text": "The LORD is my shepherd; I shall not want.",
    "book": "Psalms",
    "chapter": 23,
    "verse_number": 1,
    "version": "KJV",
    "testament": "OT"
  },
  "results": [...]
}
```

---

## Adding more Bible versions (NIV, ESV, etc.)

1. Obtain a JSON file in the same format as KJV
2. Edit `scripts/load_kjv.py` — call `load_from_json(data, version_code="NIV")`
3. Re-run the loader

> Note: NIV and ESV are copyrighted. KJV is public domain. Check licensing before distribution.

---

## Phase 2 — Semantic search (future upgrade)

When fuzzy matching isn't enough (paraphrases, different translations), upgrade to vector search:

```bash
pip install pgvector openai
```

1. Add `pgvector` to PostgreSQL
2. Add an `embedding` column to the `Verse` model
3. Pre-compute embeddings with `text-embedding-3-small` (~$0.80 for the whole KJV)
4. Replace `fetch_candidates` in `bible/matching.py` with a cosine similarity query

This enables: "God loved the world so much he gave his son" → John 3:16 ✓

---

## Deployment checklist

- [ ] Set `DEBUG=False` in `.env`
- [ ] Set a real `DJANGO_SECRET_KEY`
- [ ] Set `ALLOWED_HOSTS` to your domain
- [ ] Run `python manage.py collectstatic`
- [ ] Use gunicorn + nginx (not `runserver`)
- [ ] Set `CORS_ALLOWED_ORIGINS` to your frontend domain
- [ ] Switch to `SESSION_COOKIE_SECURE=True` for HTTPS

---

## Acknowledgements
- KJV data: [aruljohn/Bible-kjv](https://github.com/aruljohn/Bible-kjv) (MIT)
- Fuzzy matching: [rapidfuzz](https://github.com/rapidfuzz/RapidFuzz)
- Transcription: [OpenAI Whisper](https://openai.com/research/whisper)