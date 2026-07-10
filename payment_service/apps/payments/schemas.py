"""
Pydantic schemas for Payment service.
"""

from pydantic import BaseModel
from decimal import Decimal
from datetime import datetime
from uuid import UUID
from typing import Optional


# ──────────────────────────────────────────────
# Request schemas
# ──────────────────────────────────────────────

class InitiatePaymentRequest(BaseModel):
    """
    Called internally by Order service.
    Amount in rupees — we convert to paise internally.
    """
    order_id: UUID
    amount: Decimal     # in rupees e.g. 2999.00
    currency: str = "INR"


# ──────────────────────────────────────────────
# Response schemas
# ──────────────────────────────────────────────

class InitiatePaymentResponse(BaseModel):
    data: dict
    message: str


class PaymentStatusResponse(BaseModel):
    payment_id: UUID
    order_id: UUID
    status: str
    amount: int          # in paise
    currency: str
    payment_method: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class PaymentStatusEnvelope(BaseModel):
    data: PaymentStatusResponse
    message: str


class MessageResponse(BaseModel):
    message: str