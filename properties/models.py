from django.contrib.gis.db import models
from django.utils.text import slugify
from pgvector.django import HnswIndex, VectorField
import uuid


class Location(models.Model):
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=10, unique=True, help_text="ISO country code, e.g. BD, US")
    center = models.PointField(
        geography=True,
        srid=4326,
        null=True,
        blank=True,
        help_text="Country center point",
    )
    embedding = VectorField(
        dimensions=384,
        null=True,
        blank=True,
        help_text="Semantic embedding of location name (all-MiniLM-L6-v2)",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Location"
        verbose_name_plural = "Locations"
        indexes = [
            HnswIndex(
                name="location_embedding_hnsw_idx",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"


class Property(models.Model):

    class PropertyType(models.TextChoices):
        VILLA = "villa", "Villa"
        COTTAGE = "cottage", "Cottage"
        APARTMENT = "apartment", "Apartment"
        CABIN = "cabin", "Cabin"
        BUNGALOW = "bungalow", "Bungalow"
        HOUSE = "house", "House"

    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name="properties",
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=300, unique=True, blank=True)
    description = models.TextField(blank=True)
    property_type = models.CharField(
        max_length=20,
        choices=PropertyType.choices,
        default=PropertyType.VILLA,
    )
    bedrooms = models.PositiveSmallIntegerField(default=1)
    bathrooms = models.PositiveSmallIntegerField(default=1)
    max_guests = models.PositiveSmallIntegerField(default=2)
    price_per_night = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amenities = models.JSONField(
        default=list,
        blank=True,
        help_text='List of amenities, e.g. ["WiFi", "Pool", "Kitchen"]',
    )
    center = models.PointField(geography=True, srid=4326, null=True, blank=True)
    embedding = VectorField(
        dimensions=384,
        null=True,
        blank=True,
        help_text="Semantic embedding from all-MiniLM-L6-v2 (384d)",
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

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)
            slug = base
            if Property.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{uuid.uuid4().hex[:6]}"
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    @property
    def primary_image(self):
        return self.images.first()


class PropertyImage(models.Model):
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.ImageField(upload_to="properties/%Y/%m/", blank=True, null=True)
    url = models.URLField(max_length=500, blank=True)
    caption = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "Property Image"
        verbose_name_plural = "Property Images"

    def __str__(self):
        return self.caption or f"Image for {self.property.name}"

    def get_src(self):
        """Returns the image URL regardless of whether it's a file upload or external URL."""
        if self.image:
            return self.image.url
        return self.url
