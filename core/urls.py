from django.urls import path

from . import views

urlpatterns = [
    path("", views.main, name="main"),
    path('api/cities/', views.get_cities, name='get_cities'),

]
