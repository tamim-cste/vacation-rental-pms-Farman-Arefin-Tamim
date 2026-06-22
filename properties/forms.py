from django import forms
from .models import Property


PROPERTY_TYPE_CHOICES = [("", "Any Type")] + list(Property.PropertyType.choices)

BEDROOM_CHOICES = [
    ("", "Any"),
    ("1", "1+"),
    ("2", "2+"),
    ("3", "3+"),
    ("4", "4+"),
]

SORT_CHOICES = [
    ("", "Relevance"),
    ("price_asc", "Price: Low to High"),
    ("price_desc", "Price: High to Low"),
    ("newest", "Newest First"),
]


class SearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "placeholder": "Search by country, city, or property name...",
            "class": "search-input",
            "autocomplete": "off",
        }),
    )
    property_type = forms.ChoiceField(
        required=False,
        choices=PROPERTY_TYPE_CHOICES,
        widget=forms.Select(attrs={"class": "filter-select"}),
    )
    bedrooms = forms.ChoiceField(
        required=False,
        choices=BEDROOM_CHOICES,
        widget=forms.Select(attrs={"class": "filter-select"}),
    )
    min_price = forms.IntegerField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={"class": "filter-input", "placeholder": "Min $"}),
    )
    max_price = forms.IntegerField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={"class": "filter-input", "placeholder": "Max $"}),
    )
    sort = forms.ChoiceField(
        required=False,
        choices=SORT_CHOICES,
        widget=forms.Select(attrs={"class": "filter-select"}),
    )
