"""
Razorpay API client.

Wraps the official Razorpay Python SDK.
Keeps all Razorpay-specific logic in one place.

Two responsibilities:
  1. Create a Razorpay order (called at checkout)
  2. Verify webhook signature (called when webhook arrives)
"""

import os
import hmac
import hashlib
import razorpay
from dotenv import load_dotenv

load_dotenv()

RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")

# Initialize Razorpay client with your API keys
client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))


class RazorpayError(Exception):
    """Raised when Razorpay API call fails."""
    pass


def create_razorpay_order(amount_paise: int, order_id: str) -> dict:
    """
    Create a Razorpay order — required before showing the payment popup.

    amount_paise: amount in paise (₹2999 = 299900 paise)
    order_id: your internal order UUID — stored as receipt for reference

    Returns Razorpay order object with id, amount, currency.

    Why paise?
      Razorpay (and most payment gateways) work in the smallest
      currency unit to avoid decimal arithmetic entirely.
      ₹2999.00 → 299900 paise (integer, no decimals, no floating point bugs)
    """
    try:
        razorpay_order = client.order.create({
            "amount": amount_paise,
            "currency": "INR",
            "receipt": str(order_id),    # your order ID for reference
            "payment_capture": True,     # auto-capture payment on success
        })
        return razorpay_order

    except Exception as e:
        raise RazorpayError(f"Failed to create Razorpay order: {str(e)}")


def verify_webhook_signature(body: bytes, signature: str) -> bool:
    """
    Verify that a webhook request genuinely came from Razorpay.

    How it works:
      Razorpay signs every webhook payload using HMAC-SHA256 with your
      webhook secret. We recompute the signature and compare.
      If they match — it's genuinely from Razorpay.
      If not — it's a fake request, ignore it.

    This is critical security. Without this check, anyone could send
    a fake "payment succeeded" webhook and get their order marked as paid.

    body: raw request bytes (not parsed JSON — must be raw for signature to match)
    signature: value from X-Razorpay-Signature header
    """
    try:
        # Recompute HMAC-SHA256 of the raw body using webhook secret
        expected = hmac.new(
            RAZORPAY_WEBHOOK_SECRET.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()

        # Compare using constant-time comparison (prevents timing attacks)
        return hmac.compare_digest(expected, signature)

    except Exception:
        return False