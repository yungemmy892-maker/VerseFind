from django.db import models


class BibleVersion(models.Model):
    code = models.CharField(max_length=10, unique=True)  # e.g. "KJV", "NIV"
    name = models.CharField(max_length=100)
    language = models.CharField(max_length=50, default="English")

    def __str__(self):
        return self.code


class Book(models.Model):
    name = models.CharField(max_length=50)
    abbreviation = models.CharField(max_length=10)
    testament = models.CharField(
        max_length=3, choices=[("OT", "Old Testament"), ("NT", "New Testament")]
    )
    order = models.PositiveSmallIntegerField()  # 1-66

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.name


class Verse(models.Model):
    version = models.ForeignKey(BibleVersion, on_delete=models.CASCADE, related_name="verses")
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="verses")
    chapter = models.PositiveSmallIntegerField()
    verse_number = models.PositiveSmallIntegerField()
    text = models.TextField()
    # Pre-computed normalised text for fast matching
    normalized_text = models.TextField(blank=True)

    class Meta:
        unique_together = ("version", "book", "chapter", "verse_number")
        indexes = [
            models.Index(fields=["version", "book", "chapter"]),
            models.Index(fields=["normalized_text"]),
        ]

    def __str__(self):
        return f"{self.book.name} {self.chapter}:{self.verse_number} ({self.version.code})"

    @property
    def reference(self):
        return f"{self.book.name} {self.chapter}:{self.verse_number}"


class SavedVerse(models.Model):
    """User-saved verses (session-based for MVP, auth-ready for v2)."""
    session_key = models.CharField(max_length=40)
    verse = models.ForeignKey(Verse, on_delete=models.CASCADE)
    note = models.TextField(blank=True)
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-saved_at"]

    def __str__(self):
        return f"{self.session_key[:8]}… → {self.verse}"