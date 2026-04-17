from django.contrib import admin
from .models import BibleVersion, Book, Verse, SavedVerse


@admin.register(BibleVersion)
class BibleVersionAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "language")
    search_fields = ("code", "name")


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ("order", "name", "abbreviation", "testament")
    list_filter = ("testament",)
    ordering = ("order",)


@admin.register(Verse)
class VerseAdmin(admin.ModelAdmin):
    list_display = ("reference", "version", "text_preview")
    list_filter = ("version", "book__testament")
    search_fields = ("text", "book__name")
    readonly_fields = ("normalized_text",)

    def text_preview(self, obj):
        return obj.text[:80] + "…" if len(obj.text) > 80 else obj.text
    text_preview.short_description = "Text"


@admin.register(SavedVerse)
class SavedVerseAdmin(admin.ModelAdmin):
    list_display = ("verse", "session_key", "saved_at")
    list_filter = ("saved_at",)
    readonly_fields = ("saved_at",)