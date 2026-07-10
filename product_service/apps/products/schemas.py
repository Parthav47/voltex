"""
Pydantic schemas for Product service.

New pattern here — we have separate schemas for:
  - Public responses (what users see) — full product detail
  - List responses (what users see in listings) — trimmed, no SEO fields
  - Internal responses (what Order service sees) — includes stock_count
  - Admin requests (what admin sends to update stock) — just the count
"""

from pydantic import BaseModel, field_validator
from decimal import Decimal
from datetime import datetime
from uuid import UUID
from typing import Optional
from typing import List


# ──────────────────────────────────────────────
# Request schemas
# ──────────────────────────────────────────────

class StockUpdateRequest(BaseModel):
    """
    Used by Order service to update stock after checkout.
    Only field needed — the new stock count.
    """
    stock_count: int

    @field_validator("stock_count")
    @classmethod
    def stock_must_not_be_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Stock count cannot be negative")
        return v


# ──────────────────────────────────────────────
# Response schemas
# ──────────────────────────────────────────────

class ProductListResponse(BaseModel):
    """
    Trimmed product data for listing pages.
    No description, no SEO fields — keeps the response lean.
    """
    id: UUID
    name: str
    sku: str
    price: Decimal
    stock_count: int
    images: List[str]
    is_active: bool

    model_config = {"from_attributes": True}


class ProductDetailResponse(BaseModel):
    """
    Full product data for the product detail page.
    Includes all fields including description and SEO.
    """
    id: UUID
    name: str
    sku: str
    description: str
    price: Decimal
    stock_count: int
    images: List[str]
    weight_grams: int
    dimensions: str
    meta_title: str
    meta_description: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProductListEnvelope(BaseModel):
    data: List[ProductListResponse]
    message: str


class ProductDetailEnvelope(BaseModel):
    data: ProductDetailResponse
    message: str


class StockUpdateEnvelope(BaseModel):
    data: dict
    message: str


class MessageResponse(BaseModel):
    message: str