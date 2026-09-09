# dashboard/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard_main, name="dashboard"),
    path("content/<str:page>/", views.dashboard_content, name="dashboard_content"),
    path("profile/", views.profile_view, name="profile_view"),
    path(
        "application/<int:pk>/action/",
        views.application_action,
        name="application_action",
    ),
    path("generate-password/", views.generate_password, name="generate_password"),
    path(
        "submit-new-application/",
        views.submit_new_application,
        name="submit_new_application",
    ),
    path("submit-add-student/", views.submit_add_student, name="submit_add_student"),
    path(
        "program-apply-request/",
        views.program_apply_request,
        name="program_apply_request",
    ),
    path("get-cities/", views.get_cities_by_country, name="get_cities_by_country"),
    path("programs-search/", views.programs_search, name="programs_search"),
    path("universities-search/", views.universities_search, name="universities_search"),
    path(
        "export/universities/",
        views.export_universities_pdf,
        name="export_universities_pdf",
    ),
    path("export/programs/", views.export_programs_pdf, name="export_programs_pdf"),
    # Notification URLs
    path("notifications/send/", views.send_notification, name="send_notification"),
    path("notifications/search-users/", views.search_users_for_notification, name="search_users_for_notification"),
    path("notifications/get-group-users/", views.get_group_user_ids, name="get_group_user_ids"),
    path("notifications/unread-count/", views.get_unread_notification_count, name="unread_notification_count"),
    path("notifications/mark-all-read/", views.mark_all_notifications_read, name="mark_all_notifications_read"),
    path("notifications/mark-read/<int:pk>/", views.mark_notification_read, name="mark_notification_read"),
    path("notifications/delete/<int:pk>/", views.delete_notification, name="delete_notification"),
    path("notifications/detail/<int:pk>/", views.notification_detail, name="notification_detail"),
]
