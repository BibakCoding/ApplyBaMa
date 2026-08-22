#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""

    # 1. Load environment variables from the .env file automatically
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        # If python-dotenv is not installed, it safely skips this step
        # and relies on actual OS environment variables.
        pass

    # 2. Set the default Django settings module
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ApplyBaMa.settings.dev')

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate your virtual environment?"
        ) from exc

    # 3. Execute the command
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
