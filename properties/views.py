from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib.gis.db.models.functions import Distance

from .models import Property, Location
from .forms import SearchForm


def home(request):
    """Homepage with search form and featured properties."""
    form = SearchForm()
    featured = (
        Property.objects.select_related("location")
        .prefetch_related("images")
        .order_by("-created_at")[:6]
    )
    locations = Location.objects.order_by("name")
    context = {
        "form": form,
        "featured_properties": featured,
        "locations": locations,
        "total_properties": Property.objects.count(),
        "total_locations": Location.objects.count(),
    }
    return render(request, "properties/home.html", context)


def property_list(request):
    """Search results / listing page with filters and pagination."""
    form = SearchForm(request.GET)
    queryset = (
        Property.objects.select_related("location")
        .prefetch_related("images")
    )

    if form.is_valid():
        q = form.cleaned_data.get("q", "").strip()
        if q:
            queryset = queryset.filter(
                Q(name__icontains=q)
                | Q(description__icontains=q)
                | Q(location__name__icontains=q)
                | Q(location__code__iexact=q)
            )

        property_type = form.cleaned_data.get("property_type")
        if property_type:
            queryset = queryset.filter(property_type=property_type)

        bedrooms = form.cleaned_data.get("bedrooms")
        if bedrooms:
            queryset = queryset.filter(bedrooms__gte=int(bedrooms))

        min_price = form.cleaned_data.get("min_price")
        if min_price is not None:
            queryset = queryset.filter(price_per_night__gte=min_price)

        max_price = form.cleaned_data.get("max_price")
        if max_price is not None:
            queryset = queryset.filter(price_per_night__lte=max_price)

        sort = form.cleaned_data.get("sort")
        if sort == "price_asc":
            queryset = queryset.order_by("price_per_night")
        elif sort == "price_desc":
            queryset = queryset.order_by("-price_per_night")
        elif sort == "newest":
            queryset = queryset.order_by("-created_at")
        else:
            queryset = queryset.order_by("-created_at")

    total_results = queryset.count()
    paginator = Paginator(queryset, 9)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "form": form,
        "page_obj": page_obj,
        "total_results": total_results,
        "query": request.GET.get("q", ""),
    }
    return render(request, "properties/listing.html", context)


def property_detail(request, slug):
    """Property detail page with distance from city center."""
    # Annotate with distance from country center (PostGIS ST_Distance)
    prop = get_object_or_404(
        Property.objects.select_related("location").prefetch_related("images"),
        slug=slug,
    )

    # Calculate distance from city center using PostGIS
    distance_km = None
    if prop.center and prop.location.center:
        annotated = (
            Property.objects.filter(pk=prop.pk)
            .annotate(city_distance=Distance("center", "location__center"))
            .first()
        )
        if annotated and annotated.city_distance:
            distance_km = round(annotated.city_distance.m / 1000, 1)

    # Similar properties (same location, excluding current)
    similar = (
        Property.objects.filter(location=prop.location)
        .exclude(pk=prop.pk)
        .prefetch_related("images")
        .order_by("-created_at")[:3]
    )

    context = {
        "property": prop,
        "distance_km": distance_km,
        "similar_properties": similar,
        "all_images": list(prop.images.all()),
    }
    return render(request, "properties/detail.html", context)