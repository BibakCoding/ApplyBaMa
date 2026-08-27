# dashboard/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard_main, name="dashboard"),
    path('content/<str:page>/', views.dashboard_content, name='dashboard_content'),
    path('profile/', views.profile_view, name='profile_view'),
    path('application/<int:pk>/action/', views.application_action, name='application_action'),
    path('generate-password/', views.generate_password, name='generate_password'),
    path('submit-new-application/', views.submit_new_application, name='submit_new_application'),
    path('submit-add-student/', views.submit_add_student, name='submit_add_student'),
    path('program-apply-request/', views.program_apply_request, name='program_apply_request'),
    path('get-cities/', views.get_cities_by_country, name='get_cities_by_country'),
]
