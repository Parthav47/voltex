"""
Notification model.

Records every notification attempt — what was sent,
to whom, when, and whether it succeeded.

This is important for:
  - Debugging ("did the email actually go out?")
  - Auditing ("prove we sent the confirmation")
  - Retry logic later (query status="failed" and resend)
"""

import uuid
from django.db import models


class Notification(models.Model):
    STATUS_QUEUED = "queued"
    STATUS_SENT = "sent"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_QUEUED, "Queued"),
        (STATUS_SENT, "Sent"),
        (STATUS_FAILED, "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # What triggered this notification
    event_type = models.CharField(max_length=100)  # "payment_success", "order_placed"

    # Who it was sent to — no FK, different service
    user_id = models.UUIDField(db_index=True)
    user_email = models.EmailField()

    # Related order
    order_id = models.UUIDField(db_index=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_QUEUED,
    )

    # Full event payload — stored so we can debug exactly what was sent
    payload = models.JSONField(default=dict)

    # Error message if sending failed
    error = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    # When it was actually sent (None if not sent yet)
    sent_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "notifications"

    def __str__(self):
        return f"{self.event_type} → {self.user_email} ({self.status})"