from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("logout/", views.logout_view, name="logout"),
    path("confirm_code/<int:pk>/", views.confirm_code, name="confirm_code"),
    path("resend_code/<int:pk>/", views.resend_code, name="resend_code"),
    path("forget_password/", views.forget_password, name="forget_password"),
    path("change_password/<str:token>/", views.change_password, name="change_password"),
    path("username-selection/", views.username_selection, name="username_selection"),
]
