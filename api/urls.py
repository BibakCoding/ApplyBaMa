# ApplyBaMa/api/urls.py

from django.urls import path
from . import views  # assuming your city_list_api view lives in api/views.py

urlpatterns = [
    path("cities/", views.city_list_api, name="api-cities"),
]
