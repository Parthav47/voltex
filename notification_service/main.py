"""
Notification service entry point.

Unlike other services, this has NO HTTP server.
It runs a single blocking loop that listens to Redis.

Run with:
  python main.py
"""

import os
import django
from dotenv import load_dotenv

load_dotenv()

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.notifications.event_consumer import run

if __name__ == "__main__":
    run()