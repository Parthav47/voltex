"""
event_consumer.py

The heart of the Notification service.
Subscribes to Redis pub/sub and reacts to payment events.

This is the ONLY entry point — no HTTP, no API.
The service does exactly one thing: listen and send emails.

Architecture note:
  This is a pure event-driven consumer. It knows nothing about
  Order service or Payment service internals. It only knows about
  the event shape (the JSON payload format). This loose coupling
  is exactly what makes microservices maintainable — you can
  change how payments work without touching notification logic.
"""

import os
import json
import redis
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")


def _get_user_info(user_id: str) -> dict:
    """
    Fetch user info from Auth service to get email and name.

    In a real system this would be included in the event payload
    by the publishing service. For simplicity we call Auth service
    directly here — but the event payload approach is better practice.

    For now we use a fallback if the call fails.
    """
    import urllib.request
    import urllib.error

    AUTH_SERVICE_URL = os.environ.get("AUTH_SERVICE_URL", "http://localhost:8001")

    try:
        # We can't use JWT here (no user context) so Auth service
        # would need an internal endpoint — for now return placeholder
        # The order event should ideally include user_email directly
        return {"email": None, "name": "Customer"}
    except Exception:
        return {"email": None, "name": "Customer"}


def handle_payment_success(data: dict) -> None:
    """
    Handle payment_success event.

    Expected data shape:
      {
        "order_id": "uuid",
        "payment_id": "uuid",
        "amount": 299900,         ← in paise
        "user_email": "...",      ← included by publisher
        "user_name": "...",       ← included by publisher
      }

    Sends order confirmation email and records the notification.
    """
    from apps.notifications.models import Notification
    from apps.notifications.email_sender import send_order_confirmation

    order_id = data.get("order_id", "")
    amount = data.get("amount", 0)
    user_email = data.get("user_email", "")
    user_name = data.get("user_name", "Customer")

    # Create notification record with status=queued
    notification = Notification.objects.create(
        event_type="payment_success",
        user_id=data.get("user_id", "00000000-0000-0000-0000-000000000000"),
        user_email=user_email or "unknown@example.com",
        order_id=order_id,
        status=Notification.STATUS_QUEUED,
        payload=data,
    )

    if not user_email:
        print(f"⚠ No email in payload for order {order_id} — skipping send")
        notification.status = Notification.STATUS_FAILED
        notification.error = "No user_email in event payload"
        notification.save(update_fields=["status", "error"])
        return

    try:
        send_order_confirmation(
            to_email=user_email,
            user_name=user_name,
            order_id=order_id,
            amount=amount,
        )
        notification.status = Notification.STATUS_SENT
        notification.sent_at = datetime.now(timezone.utc)
        notification.save(update_fields=["status", "sent_at"])
        print(f"✓ Confirmation email sent to {user_email} for order {order_id[:8]}")

    except Exception as e:
        notification.status = Notification.STATUS_FAILED
        notification.error = str(e)
        notification.save(update_fields=["status", "error"])
        print(f"✗ Failed to send email for order {order_id}: {e}")


def run():
    """
    Main loop — connects to Redis and listens forever.

    This is called directly from main.py.
    Unlike Order service (which runs the consumer in a background thread),
    Notification service IS the consumer — it has no HTTP server,
    so the main thread itself runs this loop.
    """
    print("Starting Notification service...")

    r = redis.from_url(REDIS_URL)
    pubsub = r.pubsub()
    pubsub.subscribe("payment_events")

    print("✓ Notification service listening for payment events...")
    print("  Press Ctrl+C to stop\n")

    for message in pubsub.listen():
        if message["type"] != "message":
            continue

        try:
            payload = json.loads(message["data"])
            event_type = payload.get("event")
            data = payload.get("data", {})

            print(f"→ Event received: {event_type}")

            if event_type == "payment_success":
                handle_payment_success(data)
            else:
                print(f"  Unhandled event type: {event_type}")

        except Exception as e:
            print(f"✗ Error processing event: {e}")