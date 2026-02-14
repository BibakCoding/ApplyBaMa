from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard_main, name="dashboard"),
    path('content/<str:page>/', views.dashboard_content, name='dashboard_content'),
    path('profile/', views.profile_view, name='profile_view'),
]