"""
Management command to pre-build the phonetic index.
Run after loading Bible data.

Usage:
    python manage.py build_phonetic_index
"""
from django.core.management.base import BaseCommand
from bible.matching import build_phonetic_index


class Command(BaseCommand):
    help = "Pre-builds the Soundex phonetic index for fast verse matching"

    def handle(self, *args, **options):
        self.stdout.write("Building phonetic index...")
        build_phonetic_index()
        self.stdout.write(self.style.SUCCESS("Phonetic index built successfully."))