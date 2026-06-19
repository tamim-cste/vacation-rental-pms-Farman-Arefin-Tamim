from django.contrib import admin
from django.utils.html import format_html

from .models import Location, Property, PropertyImage


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 1
    fields = ("preview", "image", "url", "caption")
    readonly_fields = ("preview",)

    def preview(self, obj):
        src = obj.image.url if obj.image else obj.url
        if not src:
            return "—"
        return format_html(
            '<img src="{}" style="height:60px;width:80px;object-fit:cover;border-radius:4px;" />',
            src,
        )

    preview.short_description = "Preview"


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "property_count", "created_at")
    search_fields = ("name", "code")
    list_filter = ("created_at",)
    ordering = ("name",)

    @admin.display(description="Properties")
    def property_count(self, obj):
        return obj.properties.count()


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ("name", "location", "thumbnail", "has_embedding", "created_at")
    list_filter = ("location", "created_at")
    search_fields = ("name", "description")
    autocomplete_fields = ("location",)
    readonly_fields = ("created_at", "updated_at")
    inlines = [PropertyImageInline]

    @admin.display(description="Image")
    def thumbnail(self, obj):
        first_image = obj.images.first()
        if not first_image:
            return "—"
        src = first_image.image.url if first_image.image else first_image.url
        if not src:
            return "—"
        return format_html(
            '<img src="{}" style="height:40px;width:60px;object-fit:cover;border-radius:4px;" />',
            src,
        )

    @admin.display(boolean=True, description="Has embedding")
    def has_embedding(self, obj):
        return obj.embedding is not None
