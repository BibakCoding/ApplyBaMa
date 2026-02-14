"""
Settings module package.
By default, use development settings.
"""
import os

# Default to dev settings
if os.getenv('DJANGO_SETTINGS_MODULE') is None:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ApplyBaMa.settings.dev')
