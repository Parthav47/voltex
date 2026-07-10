"""
Pydantic schemas for Order service.
"""

from pydantic import BaseModel, field_validator
from decimal import Decimal
from datetime import datetime
from uuid import UUID
from typing import List, Optional


# ──────────────────────────────────────────────
# Request schemas
# ──────────────────────────────────────────────

class AddToCartRequest(BaseModel):
    product_id: UUID
    quantity: int

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Quantity must be at least 1")
        return v


class UpdateCartItemRequest(BaseModel):
    quantity: int

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Quantity cannot be negative")
        return v


class CheckoutRequest(BaseModel):
    """Shipping address provided at checkout."""
    shipping_name: str
    shipping_address_line1: str
    shipping_address_line2: str = ""
    shipping_city: str
    shipping_state: str
    shipping_pincode: str
    shipping_phone: str

    @field_validator("shipping_pincode")
    @classmethod
    def pincode_must_be_valid(cls, v: str) -> str:
        if not v.isdigit() or len(v) != 6:
            raise ValueError("Pincode must be 6 digits")
        return v

    @field_validator("shipping_phone")
    @classmethod
    def phone_must_be_valid(cls, v: str) -> str:
        digits = v.replace("+", "").replace("-", "").replace(" ", "")
        if not digits.isdigit() or len(digits) < 10:
            raise ValueError("Invalid phone number")
        return v


# ──────────────────────────────────────────────
# Response schemas
# ──────────────────────────────────────────────

class CartItemResponse(BaseModel):
    cart_item_id: UUID
    product_id: UUID
    product_name: str
    unit_price: Decimal
    quantity: int
    subtotal: Decimal

    model_config = {"from_attributes": True}


class CartResponse(BaseModel):
    cart_id: UUID
    items: List[CartItemResponse]
    total: Decimal


class CartEnvelope(BaseModel):
    data: CartResponse
    message: str


class AddToCartEnvelope(BaseModel):
    data: dict
    message: str


class OrderItemResponse(BaseModel):
    product_id: UUID
    product_name: str
    product_sku: str
    quantity: int
    unit_price: Decimal

    model_config = {"from_attributes": True}


class ShippingAddressResponse(BaseModel):
    name: str
    address_line1: str
    address_line2: str
    city: str
    state: str
    pincode: str
    phone: str


class OrderResponse(BaseModel):
    order_id: UUID
    status: str
    total_amount: Decimal
    items: List[OrderItemResponse]
    shipping_address: ShippingAddressResponse
    created_at: datetime

    model_config = {"from_attributes": True}


class OrderListItemResponse(BaseModel):
    order_id: UUID
    status: str
    total_amount: Decimal
    created_at: datetime

    model_config = {"from_attributes": True}


class CheckoutEnvelope(BaseModel):
    data: dict
    message: str


class OrderEnvelope(BaseModel):
    data: OrderResponse
    message: str


class OrderListEnvelope(BaseModel):
    data: List[OrderListItemResponse]
    message: str


class MessageResponse(BaseModel):
    message: str