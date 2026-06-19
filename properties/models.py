
from django.contrib.gis.db import models
from pgvector.django import HnswIndex, VectorField


class Location(models.Model):
    """A country, for now (state/city hierarchy can be layered on later)."""

    name = models.CharField(max_length=150)
    code = models.CharField(max_length=10, unique=True, help_text="ISO country code, e.g. BD, US")
    center = models.PointField(
        geography=True,
        srid=4326,
        null=True,
        blank=True,
        help_text="Country center point (auto-filled as the centroid of its properties on import)",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Location"
        verbose_name_plural = "Locations"

    def __str__(self):
        return f"{self.name} ({self.code})"


class Property(models.Model):
    """A single vacation rental listing."""

    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name="properties",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    center = models.PointField(
        geography=True,
        srid=4326,
        null=True,
        blank=True,
        help_text="Property's geographic location",
    )
    embedding = VectorField(
        dimensions=1536,
        null=True,
        blank=True,
        help_text="Semantic-search embedding over name + description (populated later)",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Property"
        verbose_name_plural = "Properties"
        indexes = [
            HnswIndex(
                name="property_embedding_hnsw_idx",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
        ]

    def __str__(self):
        return self.name


class PropertyImage(models.Model):
    """An image attached to a Property. Managed as an inline under Property
    in the admin (see admin.py)."""

    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.ImageField(
        upload_to="properties/%Y/%m/",
        blank=True,
        null=True,
        help_text="Upload a file directly (optional if a source `url` is provided instead)",
    )
    url = models.URLField(
        max_length=500,
        blank=True,
        help_text="Source image URL, e.g. from an imported CSV dataset",
    )
    caption = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "Property Image"
        verbose_name_plural = "Property Images"

    def __str__(self):
        return self.caption or f"Image for {self.property.name}"
