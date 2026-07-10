"""
Payment model.

One table — payments.
Each row represents one payment attempt for one order.

Key fields explained:
  - gateway_order_id: the Razorpay order ID (order_xyz123)
    Created by us when we call Razorpay to initiate payment.

  - gateway_payment_id: the Razorpay payment ID (pay_abc123)
    Set by Razorpay in the webhook after user pays.
    NULL until payment completes — that's intentional and correct.

  - status lifecycle:
    initiated → success (payment captured)
    initiated → failed (payment failed or user closed popup)

  - failure_reason: Razorpay's error message if payment fails.
    Useful for debugging and showing user a helpful message.
"""

import uuid
from django.db import models


class Payment(models.Model):
    STATUS_INITIATED = "initiated"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_INITIATED, "Initiated"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # order_id from Order service — no ForeignKey (different DB)
    order_id = models.UUIDField(unique=True, db_index=True)

    # Razorpay order ID — created when we initiate payment
    # Format: "order_xyz123" — comes from Razorpay API
    gateway_order_id = models.CharField(max_length=255, unique=True)

    # Razorpay payment ID — set by webhook after user pays
    # NULL until payment completes
    gateway_payment_id = models.CharField(
        max_length=255, blank=True, null=True, unique=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_INITIATED,
        db_index=True,
    )

    # UPI, card, netbanking, wallet — set by webhook
    payment_method = models.CharField(max_length=50, blank=True, null=True)

    # Amount in PAISE (Indian currency subunit) — Razorpay uses paise
    # ₹2999 = 299900 paise. Always store as integer to avoid float issues.
    amount = models.PositiveIntegerField()

    currency = models.CharField(max_length=10, default="INR")

    # Razorpay error message if payment fails
    failure_reason = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payments"

    def __str__(self):
        return f"Payment {self.id} — {self.status}"