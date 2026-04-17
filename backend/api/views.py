"""
VerseFind API Views
===================
POST /api/identify/      — match text to a verse
POST /api/transcribe/    — audio -> text (Whisper)
GET  /api/verse/         — fetch full verse + context
GET  /api/chapter/       — fetch full chapter
GET  /api/saved/         — list saved verses
POST /api/saved/         — save a verse
DELETE /api/saved/<id>/  — remove saved verse
GET  /api/versions/      — list available Bible versions
"""

import json
import tempfile
import os

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from bible.matching import find_verse, get_context_verses, normalize
from bible.models import Verse, BibleVersion, SavedVerse, Book


# --------------------------------------------------------------------------- #
#  Core: Identify a verse from text
# --------------------------------------------------------------------------- #

@api_view(["POST"])
def identify_verse(request):
    """
    Body: { "text": "for god so loved the world", "version": "KJV" }
    Returns best match(es) with confidence scores.
    """
    data = request.data
    text = data.get("text", "").strip()
    version = data.get("version", "KJV").upper()

    if not text:
        return Response({"error": "text is required"}, status=status.HTTP_400_BAD_REQUEST)

    if len(text) < 4:
        return Response({"error": "Query too short — please enter more of the verse"}, status=400)

    result = find_verse(text, version_code=version)

    return Response(result, status=status.HTTP_200_OK)


# --------------------------------------------------------------------------- #
#  Transcription: Audio -> Text via Whisper
# --------------------------------------------------------------------------- #

@api_view(["POST"])
def transcribe_audio(request):
    """
    Multipart: audio file in request.FILES["audio"]
    Returns: { "text": "transcribed verse text" }

    Supports:
      - OpenAI Whisper API (set OPENAI_API_KEY in .env)
      - Local whisper (pip install openai-whisper, set USE_LOCAL_WHISPER=True)
      - Fallback: returns placeholder for development
    """
    from django.conf import settings

    audio_file = request.FILES.get("audio")
    if not audio_file:
        return Response({"error": "audio file required"}, status=400)

    # Validate file type
    allowed_types = ["audio/webm", "audio/mp4", "audio/mpeg", "audio/wav", "audio/ogg", "audio/m4a"]
    if audio_file.content_type not in allowed_types:
        return Response({"error": f"Unsupported audio format: {audio_file.content_type}"}, status=400)

    try:
        # Option A: OpenAI Whisper API
        if settings.OPENAI_API_KEY and not settings.USE_LOCAL_WHISPER:
            import openai
            client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
                for chunk in audio_file.chunks():
                    tmp.write(chunk)
                tmp_path = tmp.name

            try:
                with open(tmp_path, "rb") as f:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=f,
                        language="en",
                    )
                return Response({"text": transcript.text, "source": "whisper-api"})
            finally:
                os.unlink(tmp_path)

        # Option B: Local whisper
        elif settings.USE_LOCAL_WHISPER:
            import whisper

            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
                for chunk in audio_file.chunks():
                    tmp.write(chunk)
                tmp_path = tmp.name

            try:
                model = whisper.load_model("base")
                result = model.transcribe(tmp_path, language="en")
                return Response({"text": result["text"].strip(), "source": "whisper-local"})
            finally:
                os.unlink(tmp_path)

        # Dev fallback
        else:
            return Response({
                "text": "",
                "source": "none",
                "warning": "No transcription service configured. Set OPENAI_API_KEY in .env or USE_LOCAL_WHISPER=True"
            })

    except Exception as e:
        return Response({"error": f"Transcription failed: {str(e)}"}, status=500)


# --------------------------------------------------------------------------- #
#  Verse detail + context
# --------------------------------------------------------------------------- #

@api_view(["GET"])
def get_verse(request):
    """
    ?book=John&chapter=3&verse=16&version=KJV&context=3
    Returns verse + surrounding context verses.
    """
    book_name = request.query_params.get("book", "")
    chapter = request.query_params.get("chapter", 0)
    verse_num = request.query_params.get("verse", 0)
    version = request.query_params.get("version", "KJV")
    window = int(request.query_params.get("context", 3))

    try:
        verse = Verse.objects.select_related("book", "version").get(
            book__name=book_name,
            chapter=int(chapter),
            verse_number=int(verse_num),
            version__code=version,
        )
    except Verse.DoesNotExist:
        return Response({"error": "Verse not found"}, status=404)

    context = get_context_verses(book_name, int(chapter), int(verse_num), version, window)

    return Response({
        "verse": _serialize_verse(verse),
        "context": [_serialize_verse(v) for v in context],
    })


@api_view(["GET"])
def get_chapter(request):
    """
    ?book=John&chapter=3&version=KJV
    Returns all verses in a chapter.
    """
    book_name = request.query_params.get("book", "")
    chapter = request.query_params.get("chapter", 1)
    version = request.query_params.get("version", "KJV")

    verses = Verse.objects.filter(
        book__name=book_name,
        chapter=int(chapter),
        version__code=version,
    ).select_related("book", "version").order_by("verse_number")

    if not verses.exists():
        return Response({"error": "Chapter not found"}, status=404)

    return Response({
        "book": book_name,
        "chapter": int(chapter),
        "version": version,
        "verses": [_serialize_verse(v) for v in verses],
    })


# --------------------------------------------------------------------------- #
#  Saved verses (session-based)
# --------------------------------------------------------------------------- #

@api_view(["GET", "POST"])
def saved_verses(request):
    if not request.session.session_key:
        request.session.create()
    session_key = request.session.session_key

    if request.method == "GET":
        saved = SavedVerse.objects.filter(session_key=session_key).select_related(
            "verse__book", "verse__version"
        )
        return Response([
            {
                "id": s.id,
                "verse": _serialize_verse(s.verse),
                "note": s.note,
                "saved_at": s.saved_at.isoformat(),
            }
            for s in saved
        ])

    elif request.method == "POST":
        verse_id = request.data.get("verse_id")
        note = request.data.get("note", "")

        try:
            verse = Verse.objects.get(id=verse_id)
        except Verse.DoesNotExist:
            return Response({"error": "Verse not found"}, status=404)

        saved, created = SavedVerse.objects.get_or_create(
            session_key=session_key,
            verse=verse,
            defaults={"note": note},
        )
        return Response({
            "id": saved.id,
            "created": created,
            "verse": _serialize_verse(verse),
        }, status=201 if created else 200)


@api_view(["DELETE"])
def delete_saved(request, pk):
    if not request.session.session_key:
        return Response({"error": "No session"}, status=400)

    try:
        saved = SavedVerse.objects.get(id=pk, session_key=request.session.session_key)
        saved.delete()
        return Response({"deleted": True})
    except SavedVerse.DoesNotExist:
        return Response({"error": "Not found"}, status=404)


# --------------------------------------------------------------------------- #
#  Bible versions
# --------------------------------------------------------------------------- #

@api_view(["GET"])
def list_versions(request):
    versions = BibleVersion.objects.all().values("code", "name", "language")
    return Response(list(versions))


# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #

def _serialize_verse(verse: Verse) -> dict:
    return {
        "id": verse.id,
        "reference": verse.reference,
        "book": verse.book.name,
        "chapter": verse.chapter,
        "verse_number": verse.verse_number,
        "text": verse.text,
        "version": verse.version.code,
        "testament": verse.book.testament,
    }