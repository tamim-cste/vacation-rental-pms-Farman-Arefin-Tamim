from django.urls import path
from . import views

app_name = "properties"

urlpatterns = [
    path("",                     views.home,                  name="home"),
    path("search/",              views.property_list,         name="property_list"),
    path("semantic-search/",     views.semantic_search,       name="semantic_search"),
    path("property/<slug:slug>/",views.property_detail,       name="property_detail"),
    path("api/autocomplete/",    views.location_autocomplete, name="location_autocomplete"),
]
