"""
event_consumer.py

Listens to Redis pub/sub for payment events.
Runs as a background thread when the Order service starts.

This is the async communication pattern:
  Payment service publishes → Redis → Order service consumes
  No direct HTTP call between services.
"""

import os
import json
import threading
import redis
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")


def handle_payment_success(data: dict):
    """Update order status to paid when payment succeeds."""
    order_id = data.get("order_id")
    if not order_id:
        return

    try:
        from apps.orders.service import update_order_status
        from apps.orders.models import Order
        update_order_status(order_id, Order.STATUS_PAID)
        print(f"✓ Order {order_id} marked as paid")
    except Exception as e:
        print(f"✗ Failed to update order {order_id}: {e}")


def handle_payment_failed(data: dict):
    """Update order status to failed when payment fails."""
    order_id = data.get("order_id")
    if not order_id:
        return

    try:
        from apps.orders.service import update_order_status
        from apps.orders.models import Order
        update_order_status(order_id, Order.STATUS_FAILED)
        print(f"✗ Order {order_id} marked as failed")
    except Exception as e:
        print(f"✗ Failed to update order {order_id}: {e}")


def start_event_consumer():
    """
    Start Redis pub/sub listener in a background thread.
    The thread runs forever, listening for payment events.

    Why a background thread?
      The main thread runs FastAPI (handling HTTP requests).
      We need a separate thread to listen to Redis simultaneously.
      threading.daemon = True means this thread dies when the main
      process exits — no orphaned processes.
    """
    def listen():
        try:
            r = redis.from_url(REDIS_URL)
            pubsub = r.pubsub()
            pubsub.subscribe("payment_events")
            print("✓ Order service listening for payment events...")

            for message in pubsub.listen():
                # pubsub.listen() yields a subscription confirmation first
                # then actual messages — filter by type
                if message["type"] != "message":
                    continue

                try:
                    payload = json.loads(message["data"])
                    event_type = payload.get("event")
                    data = payload.get("data", {})

                    if event_type == "payment_success":
                        handle_payment_success(data)
                    elif event_type == "payment_failed":
                        handle_payment_failed(data)

                except Exception as e:
                    print(f"Event processing error: {e}")

        except Exception as e:
            print(f"Redis connection failed: {e}")

    thread = threading.Thread(target=listen, daemon=True)
    thread.start()