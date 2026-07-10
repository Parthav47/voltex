"""
Payment service — business logic.

Two main flows:
  1. Initiate: Order service calls us → we create Razorpay order → return order_id
  2. Webhook: Razorpay calls us → we verify → update payment → publish event
"""

import os
import json
import redis
from dotenv import load_dotenv
from django.core.exceptions import ObjectDoesNotExist

from .models import Payment
from .razorpay_client import create_razorpay_order, verify_webhook_signature, RazorpayError

load_dotenv()

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")


class PaymentNotFoundError(Exception):
    pass

class InvalidWebhookError(Exception):
    pass

class PaymentInitiationError(Exception):
    pass


def initiate_payment(order_id: str, amount_rupees: float) -> dict:
    """
    Create a Razorpay order for a given internal order.

    Converts rupees to paise (multiply by 100) because
    Razorpay works in the smallest currency unit.

    Returns razorpay_order_id which frontend uses to open the payment popup.
    """
    # Convert rupees to paise — Razorpay requires integer paise
    # float(2999.00) * 100 could give 299900.0000001 due to floating point
    # So we round to be safe
    amount_paise = round(float(amount_rupees) * 100)

    try:
        razorpay_order = create_razorpay_order(amount_paise, order_id)
    except RazorpayError as e:
        raise PaymentInitiationError(str(e))

    # Save payment record with status=initiated
    payment = Payment.objects.create(
        order_id=order_id,
        gateway_order_id=razorpay_order["id"],
        amount=amount_paise,
        currency="INR",
        status=Payment.STATUS_INITIATED,
    )

    return {
        "payment_id": str(payment.id),
        "razorpay_order_id": razorpay_order["id"],
        "amount": amount_paise,
        "currency": "INR",
        "razorpay_key_id": os.environ.get("RAZORPAY_KEY_ID", ""),
    }


def handle_webhook(raw_body: bytes, signature: str) -> None:
    """
    Process a Razorpay webhook event.

    Steps:
      1. Verify signature — reject if invalid
      2. Parse event type
      3. Update payment record
      4. Publish event to Redis for Order and Notification services

    raw_body must be the RAW request bytes — not parsed JSON.
    Parsing before verification would break the signature check.
    """
    # Step 1 — Verify signature before doing anything
    if not verify_webhook_signature(raw_body, signature):
        raise InvalidWebhookError("Invalid webhook signature")

    # Step 2 — Parse the payload
    payload = json.loads(raw_body)
    event = payload.get("event")
    payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})

    gateway_order_id = payment_entity.get("order_id")
    gateway_payment_id = payment_entity.get("id")
    payment_method = payment_entity.get("method")

    # Step 3 — Find and update the payment record
    try:
        payment = Payment.objects.get(gateway_order_id=gateway_order_id)
    except ObjectDoesNotExist:
        # Unknown order — ignore gracefully
        return

    if event == "payment.captured":
        payment.status = Payment.STATUS_SUCCESS
        payment.gateway_payment_id = gateway_payment_id
        payment.payment_method = payment_method
        payment.save(update_fields=[
            "status", "gateway_payment_id", "payment_method", "updated_at"
        ])

        # Step 4 — Publish event to Redis
        # Order service and Notification service listen for this
        _publish_event("payment_success", {
            "order_id": str(payment.order_id),
            "payment_id": str(payment.id),
            "amount": payment.amount,
        })

    elif event == "payment.failed":
        error_desc = payment_entity.get("error_description", "Payment failed")
        payment.status = Payment.STATUS_FAILED
        payment.failure_reason = error_desc
        payment.save(update_fields=["status", "failure_reason", "updated_at"])

        _publish_event("payment_failed", {
            "order_id": str(payment.order_id),
            "reason": error_desc,
        })


def get_payment_by_order(order_id: str) -> Payment:
    """Return payment record for a given order ID."""
    try:
        return Payment.objects.get(order_id=order_id)
    except ObjectDoesNotExist:
        raise PaymentNotFoundError(f"No payment found for order {order_id}")


def _publish_event(event_type: str, data: dict) -> None:
    """
    Publish an event to Redis pub/sub.

    Redis pub/sub works like a radio broadcast:
      - Publisher sends a message on a channel
      - All subscribers listening on that channel receive it instantly
      - If no one is listening, the message is gone (fire and forget)

    channel name: "payment_events"
    message format: {"event": "payment_success", "data": {...}}

    Order service and Notification service subscribe to "payment_events"
    and react when they receive a message.
    """
    try:
        r = redis.from_url(REDIS_URL)
        message = json.dumps({"event": event_type, "data": data})
        r.publish("payment_events", message)
        print(f"Published event: {event_type} for order {data.get('order_id')}")
    except Exception as e:
        # Don't fail the webhook response if Redis is down
        # In production you'd have a retry mechanism here
        print(f"WARNING: Failed to publish event to Redis: {e}")