"""
Generate and store embeddings for all Location and Property records.

Usage:
    # Generate embeddings for everything
    python manage.py generate_embeddings

    # Only locations
    python manage.py generate_embeddings --model location

    # Only properties
    python manage.py generate_embeddings --model property

    # Force regenerate even if embedding already exists
    python manage.py generate_embeddings --force

What it does:
    Location  → embeds location.name  (e.g. "Bangladesh")
    Property  → embeds property.name + " " + property.description
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from properties.embeddings import get_embeddings_batch
from properties.models import Location, Property


class Command(BaseCommand):
    help = "Generate semantic embeddings for Location and Property records."

    def add_arguments(self, parser):
        parser.add_argument(
            "--model",
            choices=["location", "property", "all"],
            default="all",
            help="Which model to generate embeddings for (default: all)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            default=False,
            help="Regenerate embeddings even if they already exist",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=32,
            help="Number of records to process per batch (default: 32)",
        )

    def handle(self, *args, **options):
        model_choice = options["model"]
        force = options["force"]
        batch_size = options["batch_size"]

        if model_choice in ("location", "all"):
            self._embed_locations(force, batch_size)

        if model_choice in ("property", "all"):
            self._embed_properties(force, batch_size)

    # ──────────────────────────────────────────────────────────────────────
    # Location embeddings
    # ──────────────────────────────────────────────────────────────────────
    def _embed_locations(self, force: bool, batch_size: int):
        qs = Location.objects.all()
        if not force:
            qs = qs.filter(embedding__isnull=True)

        total = qs.count()
        if total == 0:
            self.stdout.write("Locations: all embeddings already up-to-date.")
            return

        self.stdout.write(f"Generating embeddings for {total} location(s)...")
        updated = 0

        locations = list(qs)
        for i in range(0, len(locations), batch_size):
            batch = locations[i: i + batch_size]
            # Text to embed: just the location name
            texts = [loc.name for loc in batch]
            vectors = get_embeddings_batch(texts)

            with transaction.atomic():
                for loc, vec in zip(batch, vectors):
                    if vec is not None:
                        loc.embedding = vec
                        loc.save(update_fields=["embedding"])
                        updated += 1

            self.stdout.write(f"  Locations: {min(i + batch_size, total)}/{total} done", ending="\r")
            self.stdout.flush()

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(f"Locations: {updated} embedding(s) saved.")
        )

    # ──────────────────────────────────────────────────────────────────────
    # Property embeddings
    # ──────────────────────────────────────────────────────────────────────
    def _embed_properties(self, force: bool, batch_size: int):
        qs = Property.objects.select_related("location").all()
        if not force:
            qs = qs.filter(embedding__isnull=True)

        total = qs.count()
        if total == 0:
            self.stdout.write("Properties: all embeddings already up-to-date.")
            return

        self.stdout.write(f"Generating embeddings for {total} propert(ies)...")
        updated = 0

        properties = list(qs)
        for i in range(0, len(properties), batch_size):
            batch = properties[i: i + batch_size]
            # Text to embed: name + description (richer context)
            texts = [
                f"{p.name} {p.description}".strip()
                for p in batch
            ]
            vectors = get_embeddings_batch(texts)

            with transaction.atomic():
                for prop, vec in zip(batch, vectors):
                    if vec is not None:
                        prop.embedding = vec
                        prop.save(update_fields=["embedding"])
                        updated += 1

            self.stdout.write(f"  Properties: {min(i + batch_size, total)}/{total} done", ending="\r")
            self.stdout.flush()

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(f"Properties: {updated} embedding(s) saved.")
        )
