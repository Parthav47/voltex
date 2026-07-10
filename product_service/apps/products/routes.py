"""
Product service routes.

Three endpoints:
  GET  /api/products/           — public, no auth
  GET  /api/products/{id}       — public, no auth
  PATCH /api/products/{id}/stock — internal only, requires INTERNAL_API_KEY header

New concept — internal endpoint protection:
  We use a simple API key check instead of JWT.
  The Order service passes this key in the X-Internal-Key header.
  If it doesn't match, we return 403 Forbidden.
"""

import os
from uuid import UUID
from fastapi import APIRouter, HTTPException, Header, status
from dotenv import load_dotenv

from .schemas import (
    ProductListEnvelope,
    ProductDetailEnvelope,
    StockUpdateRequest,
    StockUpdateEnvelope,
)
from .service import (
    get_all_active_products,
    get_product_by_id,
    update_stock,
    ProductNotFoundError,
    OutOfStockError,
)

load_dotenv()

router = APIRouter(prefix="/api/products", tags=["Products"])

# Internal API key — must match what Order service sends
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "")


# ──────────────────────────────────────────────
# Internal key guard — reusable function
# ──────────────────────────────────────────────

def verify_internal_key(x_internal_key: str = Header(None)):
    """
    Verify the X-Internal-Key header for internal service calls.

    Header(None) means the header is optional at the HTTP level —
    we handle the missing case ourselves with a clear error message.

    Why not JWT here?
      The Order service is calling this, not a user.
      There's no "user" to put in a JWT subject.
      A shared secret key is the right tool for service-to-service auth.
    """
    if not x_internal_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "MISSING_INTERNAL_KEY",
                    "message": "X-Internal-Key header is required for this endpoint",
                }
            },
        )
    if x_internal_key != INTERNAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "INVALID_INTERNAL_KEY",
                    "message": "Invalid internal API key",
                }
            },
        )


# ──────────────────────────────────────────────
# Public routes — no auth required
# ──────────────────────────────────────────────

@router.get("/", response_model=ProductListEnvelope)
def list_products():
    """
    Return all active products.
    Public endpoint — called by landing page and product listing.
    No authentication needed — anyone can browse.
    """
    products = get_all_active_products()
    from .schemas import ProductListResponse
    return ProductListEnvelope(
        data=[ProductListResponse.model_validate(p) for p in products],
        message=f"{len(products)} product(s) found",
    )


@router.get("/{product_id}", response_model=ProductDetailEnvelope)
def get_product(product_id: UUID):
    """
    Return full detail for a single product.
    Public endpoint — called by product detail page.
    """
    try:
        product = get_product_by_id(str(product_id))
        from .schemas import ProductDetailResponse
        return ProductDetailEnvelope(
            data=ProductDetailResponse.model_validate(product),
            message="Product found",
        )
    except ProductNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "PRODUCT_NOT_FOUND",
                    "message": "Product not found or unavailable",
                }
            },
        )


# ──────────────────────────────────────────────
# Internal route — Order service only
# ──────────────────────────────────────────────

@router.patch("/{product_id}/stock", response_model=StockUpdateEnvelope)
def update_product_stock(
    product_id: UUID,
    body: StockUpdateRequest,
    x_internal_key: str = Header(None),  # reads X-Internal-Key header
):
    """
    Update stock count for a product.
    Internal only — called by Order service after checkout.
    Protected by INTERNAL_API_KEY, not JWT.
    """
    # Verify the internal key first
    verify_internal_key(x_internal_key)

    try:
        product = update_stock(str(product_id), body.stock_count)
        return StockUpdateEnvelope(
            data={"product_id": str(product.id), "stock_count": product.stock_count},
            message="Stock updated successfully",
        )
    except ProductNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "PRODUCT_NOT_FOUND",
                    "message": "Product not found",
                }
            },
        )