import os
from pathlib import Path

# Import JWT configuration
from .jwt_config import *

BASE_DIR = Path(__file__).resolve().parent.parent.parent

INSTALLED_APPS = [
    "modeltranslation",
    "solo",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core.apps.CoreConfig",
    "authentication",
    "dashboard.apps.DashboardConfig",
    "data_fetch.apps.DataFetchConfig",
    "api.apps.ApiConfig",
    "django_celery_beat",
    "rosetta",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.jwt_auth.JWTAuthenticationMiddleware",  # JWT authentication for API
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "ApplyBaMa.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
                "core.context_processors.app_config",
            ],
        },
    },
]

WSGI_APPLICATION = "ApplyBaMa.wsgi.application"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en"
TIME_ZONE = "UTC"
USE_I18N = True
USE_L10N = True
USE_TZ = True

LANGUAGES = [
    ("en", "English"),
    ("ar", "Arabic"),
    ("fa", "Farsi"),
    ("tr", "Turkish"),
]

LOCALE_PATHS = [os.path.join(BASE_DIR, "locale")]

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "core.User"
PASSWORD_RESET_TIMEOUT = 1 * 60 * 60

# Destination for @login_required, as a URL *name* rather than a path: the
# login route lives under i18n_patterns, so a hardcoded "/auth/login/" would
# lose its language prefix. Django appends the requested URL as ?next=, which
# the auth views feed back into their redirects so dashboard deep links
# (?page=profile, ?page=my_applications, ...) survive the round-trip.
LOGIN_URL = "login"

CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_BEAT_SCHEDULE = {
    "refresh-data-every-20-minutes": {
        "task": "data_fetch.tasks.refresh_universities_and_programs",
        "schedule": 20 * 60,
    },
}

SF_EMAIL = os.getenv("SF_EMAIL")
SF_PASSWORD = os.getenv("SF_PASSWORD")
