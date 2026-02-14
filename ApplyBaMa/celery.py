from celery import Celery
import os

# Set the default Django settings module for Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ApplyBaMa.settings')

# Create a Celery instance and configure it with your project name
app = Celery('ApplyBaMa')

# Load Celery settings from Django settings with the 'CELERY_' prefix
app.config_from_object('django.conf:settings', namespace='CELERY')

# Automatically discover tasks in your apps
app.autodiscover_tasks()