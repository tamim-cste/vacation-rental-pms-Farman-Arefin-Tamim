import pandas as pd
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from properties.models import Location, Property, PropertyImage

REQUIRED_COLUMNS = {"name", "country_name", "country_code", "latitude", "longitude"}


def clean(value, default=""):
    """pandas-NaN-safe string cleanup."""
    if value is None or pd.isna(value):
        return default
    return str(value).strip()


class Command(BaseCommand):
    help = "Import vacation rental properties from a CSV file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            type=str,
            default="data/sample_properties.csv",
            help="Path to the CSV file (default: data/sample_properties.csv)",
        )

    def handle(self, *args, **options):
        csv_path = options["csv"]

        try:
            df = pd.read_csv(csv_path)
        except FileNotFoundError as exc:
            raise CommandError(f"CSV file not found: {csv_path}") from exc

        missing = REQUIRED_COLUMNS - set(df.columns)
        if missing:
            raise CommandError(f"CSV is missing required column(s): {sorted(missing)}")

        locations = {}          # country_code -> Location instance
        coords_by_country = {}  # country_code -> list of (lat, lng), for centroid backfill
        created_properties = 0
        created_images = 0
        skipped_rows = 0

        with transaction.atomic():
            for row_number, row in df.iterrows():
                name = clean(row["name"])
                code = clean(row["country_code"]).upper()

                if not name or not code:
                    self.stderr.write(f"Row {row_number}: missing name/country_code, skipping.")
                    skipped_rows += 1
                    continue

                try:
                    lat, lng = float(row["latitude"]), float(row["longitude"])
                except (TypeError, ValueError):
                    self.stderr.write(f"Row {row_number}: invalid latitude/longitude, skipping.")
                    skipped_rows += 1
                    continue

                if code not in locations:
                    location, _ = Location.objects.get_or_create(
                        code=code,
                        defaults={"name": clean(row["country_name"], default=code)},
                    )
                    locations[code] = location
                    coords_by_country[code] = []

                coords_by_country[code].append((lat, lng))

                prop = Property.objects.create(
                    location=locations[code],
                    name=name,
                    description=clean(row.get("description")),
                    center=Point(lng, lat, srid=4326),
                )
                created_properties += 1

                picture_url = clean(row.get("picture_url"))
                if picture_url:
                    PropertyImage.objects.create(
                        property=prop,
                        url=picture_url,
                        caption=name,
                    )
                    created_images += 1

            # Backfill each country's center with the centroid of its properties.
            for code, coords in coords_by_country.items():
                if not coords:
                    continue
                avg_lat = sum(c[0] for c in coords) / len(coords)
                avg_lng = sum(c[1] for c in coords) / len(coords)
                locations[code].center = Point(avg_lng, avg_lat, srid=4326)
                locations[code].save(update_fields=["center"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {created_properties} properties and {created_images} images "
                f"across {len(locations)} countries. Skipped {skipped_rows} row(s)."
            )
        )
