from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Q, Case, When, IntegerField
from django.http import JsonResponse
from django.contrib.gis.db.models.functions import Distance

from .models import Property, Location
from .forms import SearchForm


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _semantic_ids(query: str) -> list[int]:
    """
    Return a priority-ordered list of Property IDs from semantic search.

    Two passes:
      1. Property embeddings — direct similarity to query
      2. Location embeddings — locations similar to query → all their properties

    Returns empty list if embeddings unavailable or model not loaded.
    """
    try:
        from pgvector.django import CosineDistance
        from properties.embeddings import build_query_embedding

        query_vec = build_query_embedding(query)
        if not query_vec:
            return []

        # Pass 1: property-level semantic match
        prop_matches = (
            Property.objects
            .filter(embedding__isnull=False)
            .annotate(sim=CosineDistance("embedding", query_vec))
            .order_by("sim")[:30]
        )
        prop_ids = [p.id for p in prop_matches]

        # Pass 2: location-level semantic match → expand to their properties
        loc_matches = (
            Location.objects
            .filter(embedding__isnull=False)
            .annotate(sim=CosineDistance("embedding", query_vec))
            .order_by("sim")[:5]
        )
        loc_prop_ids = list(
            Property.objects
            .filter(location__in=loc_matches)
            .exclude(id__in=prop_ids)
            .values_list("id", flat=True)
        )

        return prop_ids + loc_prop_ids

    except Exception:
        return []


def _merged_queryset(query: str, filters: dict):
    """
    Build a queryset that merges semantic + keyword results for `query`,
    then applies extra `filters` (property_type, bedrooms, price).

    Ordering: semantic matches first (by cosine distance rank),
              keyword-only after, newest within each group.
    """
    base_qs = (
        Property.objects
        .select_related("location")
        .prefetch_related("images")
    )

    if not query:
        qs = base_qs
    else:
        sem_ids = _semantic_ids(query)

        keyword_qs = base_qs.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(location__name__icontains=query)
            | Q(location__code__iexact=query)
        )
        keyword_ids = list(keyword_qs.values_list("id", flat=True))

        # Union: semantic first (preserves distance order), then keyword-only
        all_ids_ordered = sem_ids + [pid for pid in keyword_ids if pid not in sem_ids]

        if not all_ids_ordered:
            # No results at all — return empty qs with correct shape
            return base_qs.none()

        # Preserve ordering via CASE/WHEN
        ordering_cases = [When(id=pid, then=pos) for pos, pid in enumerate(all_ids_ordered)]
        qs = base_qs.filter(id__in=all_ids_ordered).order_by(
            Case(*ordering_cases, output_field=IntegerField()),
            "-created_at",
        )

    # Apply sidebar filters
    if filters.get("property_type"):
        qs = qs.filter(property_type=filters["property_type"])
    if filters.get("bedrooms"):
        qs = qs.filter(bedrooms__gte=int(filters["bedrooms"]))
    if filters.get("min_price") is not None:
        qs = qs.filter(price_per_night__gte=filters["min_price"])
    if filters.get("max_price") is not None:
        qs = qs.filter(price_per_night__lte=filters["max_price"])
    if filters.get("sort") == "price_asc":
        qs = qs.order_by("price_per_night")
    elif filters.get("sort") == "price_desc":
        qs = qs.order_by("-price_per_night")
    elif filters.get("sort") == "newest":
        qs = qs.order_by("-created_at")

    return qs


# ─────────────────────────────────────────────────────────────────────────────
# Views
# ─────────────────────────────────────────────────────────────────────────────

def home(request):
    """Homepage with search form and featured properties."""
    form = SearchForm()
    featured = (
        Property.objects
        .select_related("location")
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
    """
    Unified search page.

    Combines keyword search and semantic vector search (when embeddings
    are available) into a single result set, ranked by relevance.
    """
    form = SearchForm(request.GET)
    query = request.GET.get("q", "").strip()
    filters = {}

    if form.is_valid():
        filters = {
            "property_type": form.cleaned_data.get("property_type"),
            "bedrooms":       form.cleaned_data.get("bedrooms"),
            "min_price":      form.cleaned_data.get("min_price"),
            "max_price":      form.cleaned_data.get("max_price"),
            "sort":           form.cleaned_data.get("sort"),
        }

    queryset = _merged_queryset(query, filters)
    total_results = queryset.count()

    paginator = Paginator(queryset, 9)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "form": form,
        "page_obj": page_obj,
        "total_results": total_results,
        "query": query,
    }
    return render(request, "properties/listing.html", context)


def semantic_search(request):
    """
    Dedicated semantic search page.
    Combines semantic + keyword results with a branded 'AI Semantic Search' interface.
    """
    form = SearchForm(request.GET)
    query = request.GET.get("q", "").strip()
    filters = {}
    error = None

    if form.is_valid():
        filters = {
            "property_type": form.cleaned_data.get("property_type"),
            "bedrooms":       form.cleaned_data.get("bedrooms"),
            "min_price":      form.cleaned_data.get("min_price"),
            "max_price":      form.cleaned_data.get("max_price"),
            "sort":           form.cleaned_data.get("sort"),
        }

    queryset = _merged_queryset(query, filters)
    total_results = queryset.count()

    # For display: show top matched locations
    semantic_locations = []
    if query:
        try:
            from pgvector.django import CosineDistance
            from properties.embeddings import build_query_embedding
            query_vec = build_query_embedding(query)
            if query_vec:
                semantic_locations = (
                    Location.objects
                    .filter(embedding__isnull=False)
                    .annotate(similarity=CosineDistance("embedding", query_vec))
                    .order_by("similarity")[:5]
                )
        except Exception:
            pass

    paginator = Paginator(queryset, 9)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "form": form,
        "page_obj": page_obj,
        "total_results": total_results,
        "query": query,
        "semantic_locations": semantic_locations,
        "error": error,
    }
    return render(request, "properties/semantic_search.html", context)


def property_detail(request, slug):
    """Property detail page with images, amenities, and distance from city center."""
    prop = get_object_or_404(
        Property.objects.select_related("location").prefetch_related("images"),
        slug=slug,
    )

    distance_km = None
    if prop.center and prop.location.center:
        annotated = (
            Property.objects.filter(pk=prop.pk)
            .annotate(city_distance=Distance("center", "location__center"))
            .first()
        )
        if annotated and annotated.city_distance:
            distance_km = round(annotated.city_distance.m / 1000, 1)

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


# ─────────────────────────────────────────────────────────────────────────────
# API
# ─────────────────────────────────────────────────────────────────────────────

def location_autocomplete(request):
    """
    Location autocomplete API endpoint.

    GET /api/autocomplete/?q=<query>
    Returns JSON list of locations ordered by semantic similarity,
    with keyword fallback when embeddings are not available.
    """
    query = request.GET.get("q", "").strip()
    if not query or len(query) < 2:
        return JsonResponse({"results": []})

    results = []

    # Semantic search on location embeddings
    try:
        from pgvector.django import CosineDistance
        from properties.embeddings import build_query_embedding

        query_vec = build_query_embedding(query)
        if query_vec:
            locations = (
                Location.objects
                .filter(embedding__isnull=False)
                .annotate(sim=CosineDistance("embedding", query_vec))
                .order_by("sim")[:8]
            )
            results = [
                {
                    "id":             loc.id,
                    "name":           loc.name,
                    "code":           loc.code,
                    "property_count": loc.properties.count(),
                    "search_url":     f"/search/?q={loc.name}",
                }
                for loc in locations
            ]
    except Exception:
        pass

    # Keyword fallback
    if not results:
        locations = Location.objects.filter(name__icontains=query).order_by("name")[:8]
        results = [
            {
                "id":             loc.id,
                "name":           loc.name,
                "code":           loc.code,
                "property_count": loc.properties.count(),
                "search_url":     f"/search/?q={loc.name}",
            }
            for loc in locations
        ]

    return JsonResponse({"results": results, "query": query})
