#!/usr/bin/env python
"""
Django management utility.
Used for: makemigrations, migrate, and nothing else.

Usage:
  python manage.py makemigrations
  python manage.py migrate
"""

import os
import sys


def main():
    # Tell Django which settings file to use
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Make sure it's installed: pip install django"
        ) from exc

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()