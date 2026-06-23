import pandas as pd
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify
import uuid

from properties.models import Location, Property, PropertyImage

REQUIRED = {"name", "country_name", "country_code", "latitude", "longitude"}
VALID_TYPES = {c[0] for c in Property.PropertyType.choices}


def clean(value, default=""):
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def parse_pipe(value: str) -> list[str]:
    """Split a pipe-separated string into a clean list, ignoring blanks."""
    return [item.strip() for item in value.split("|") if item.strip()]


def make_slug(name, seen):
    base = slugify(name) or f"property-{uuid.uuid4().hex[:8]}"
    slug = base
    suffix = 0
    while slug in seen or Property.objects.filter(slug=slug).exists():
        suffix += 1
        slug = f"{base}-{suffix}"
    return slug


class Command(BaseCommand):
    help = "Import vacation rental properties from a CSV file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            default="data/sample_properties.csv",
            help="Path to the CSV file (default: data/sample_properties.csv)",
        )

    def handle(self, *args, **options):
        csv_path = options["csv"]
        try:
            df = pd.read_csv(csv_path)
        except FileNotFoundError as exc:
            raise CommandError(f"File not found: {csv_path}") from exc

        missing = REQUIRED - set(df.columns)
        if missing:
            raise CommandError(f"Missing required columns: {sorted(missing)}")

        locations = {}
        coords_by_country = {}
        seen_slugs = set()
        n_props = n_images = skipped = 0

        with transaction.atomic():
            for idx, row in df.iterrows():
                name = clean(row["name"])
                code = clean(row["country_code"]).upper()
                if not name or not code:
                    self.stderr.write(f"Row {idx}: missing name/country_code — skipped")
                    skipped += 1
                    continue

                try:
                    lat, lng = float(row["latitude"]), float(row["longitude"])
                except (TypeError, ValueError):
                    self.stderr.write(f"Row {idx}: invalid lat/lng — skipped")
                    skipped += 1
                    continue

                # Get or create Location
                if code not in locations:
                    loc, _ = Location.objects.get_or_create(
                        code=code,
                        defaults={"name": clean(row["country_name"], default=code)},
                    )
                    locations[code] = loc
                    coords_by_country[code] = []
                coords_by_country[code].append((lat, lng))

                # Parse optional fields
                amenities = parse_pipe(clean(row.get("amenities", "")))
                ptype = clean(row.get("property_type", ""), default="villa")
                if ptype not in VALID_TYPES:
                    ptype = "villa"

                slug = make_slug(name, seen_slugs)
                seen_slugs.add(slug)

                prop = Property.objects.create(
                    location=locations[code],
                    name=name,
                    slug=slug,
                    description=clean(row.get("description", "")),
                    property_type=ptype,
                    bedrooms=int(float(clean(row.get("bedrooms", "1"), "1") or 1)),
                    bathrooms=int(float(clean(row.get("bathrooms", "1"), "1") or 1)),
                    max_guests=int(float(clean(row.get("max_guests", "2"), "2") or 2)),
                    price_per_night=float(clean(row.get("price_per_night", "0"), "0") or 0),
                    amenities=amenities,
                    center=Point(lng, lat, srid=4326),
                )
                n_props += 1

                # ── Multiple images ────────────────────────────────────────
                # Support both old `picture_url` (single) and new
                # `picture_urls` (pipe-separated) column names.
                raw_urls = clean(row.get("picture_urls", row.get("picture_url", "")))
                image_urls = parse_pipe(raw_urls)

                for url in image_urls:
                    PropertyImage.objects.create(
                        property=prop,
                        url=url,
                        caption=name,
                    )
                    n_images += 1

            # Backfill country center points
            for code, coords in coords_by_country.items():
                if coords:
                    avg_lat = sum(c[0] for c in coords) / len(coords)
                    avg_lng = sum(c[1] for c in coords) / len(coords)
                    locations[code].center = Point(avg_lng, avg_lat, srid=4326)
                    locations[code].save(update_fields=["center"])

        self.stdout.write(self.style.SUCCESS(
            f"Imported {n_props} properties with {n_images} images "
            f"across {len(locations)} countries. Skipped {skipped} row(s)."
        ))
