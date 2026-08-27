from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
                  path("admin/", admin.site.urls),
                  path("i18n/", include("django.conf.urls.i18n")),
                  path("rosetta/", include("rosetta.urls")),
                  path("api/", include("api.urls")),
              ] + i18n_patterns(
    path("", include("core.urls")),
    path("auth/", include("authentication.urls")),
    path("dashboard/", include("dashboard.urls")),
    prefix_default_language=True,
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
