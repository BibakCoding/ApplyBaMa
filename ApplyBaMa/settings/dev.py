"""
Development settings.
"""
from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv(
    'SECRET_KEY'
)

ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    '[::1]',
    '0.0.0.0',
]

# CSRF_TRUSTED_ORIGINS = [
# ]


# Database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Email settings
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', 'djangokar.test@gmail.com')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', 'slxe vwdr kxjp fibo')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'webmaster@applybama.com')

# Cache
# CACHES = {
#     "default": {
#         "BACKEND": "django.core.cache.backends.memcached.PyMemcacheCache",
#         "LOCATION": os.getenv('CACHE_LOCATION', '127.0.0.1:11211'),
#     }
# }

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",  # ساده‌تر و بدون نیاز به سرویس خارجی
        "LOCATION": "applybama-cache",
    }
}

# Celery
# CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
# CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')


# Celery settings
# CELERY_BROKER_URL = 'filesystem://'
# CELERY_BROKER_TRANSPORT_OPTIONS = {
#     'data_folder_in': 'E:/programing/Projects/ApplyBaMa/ApplyBaMa/celery/queue',
#     'data_folder_out': 'E:/programing/Projects/ApplyBaMa/ApplyBaMa/celery/queue',
#     'data_folder_processed': 'E:/programing/Projects/ApplyBaMa/ApplyBaMa/celery/processed'
# }
# CELERY_RESULT_BACKEND = 'rpc://'

# Temporary Celery settings for development (without Redis)
CELERY_BROKER_URL = 'memory://'
CELERY_RESULT_BACKEND = 'cache+memory://'

# Run tasks synchronously during development
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
        "file": {
            "class": "logging.FileHandler",
            "filename": "debug.log",
        },
    },
    "loggers": {
        "": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": True,
        },
    },
}

# Session and CSRF settings
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
