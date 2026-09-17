# ApplyBaMa/api/urls.py

from django.urls import path
from . import views
from . import auth_views
from . import jwt_views

urlpatterns = [
    # City API
    path("cities/", views.city_list_api, name="api-cities"),

    # JWT Authentication endpoints
    path("token/", auth_views.obtain_token, name="api-token-obtain"),
    path("token/refresh/", auth_views.refresh_token, name="api-token-refresh"),
    path("token/verify/", auth_views.verify_token, name="api-token-verify"),
    path("register/", auth_views.register_user, name="api-register"),
    path("logout/", auth_views.logout_user, name="api-logout"),

    # JWT-Protected API endpoints
    path("user/profile/", jwt_views.user_profile_api, name="api-user-profile"),
    path("user/profile/update/", jwt_views.update_profile_api, name="api-user-profile-update"),
    path("dashboard/stats/", jwt_views.dashboard_stats_api, name="api-dashboard-stats"),
    path("applications/", jwt_views.my_applications_api, name="api-applications"),
    path("notifications/", jwt_views.notifications_list_api, name="api-notifications"),
]
