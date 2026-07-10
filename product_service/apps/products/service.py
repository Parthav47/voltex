"""
service.py — business logic for the Product service.

Rules for this file:
  - No FastAPI imports (no Request, Response, HTTPException)
  - No Pydantic schemas
  - Only Django ORM operations
  - Functions raise plain Python exceptions with clear messages
  - Routes catch those exceptions and convert them to HTTP responses

Why this separation?
  You can test every function here without starting an HTTP server.
  If you swap FastAPI for something else tomorrow, this file doesn't change.
"""

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction

from .models import Product


# ──────────────────────────────────────────────
# Custom exceptions
# Raised here, caught in routes.py, converted to HTTP status codes
# ──────────────────────────────────────────────

class ProductNotFoundError(Exception):
    """Raised when a product UUID doesn't exist or is inactive."""
    pass


class OutOfStockError(Exception):
    """Raised when requested quantity exceeds available stock."""
    pass


# ──────────────────────────────────────────────
# Service functions
# ──────────────────────────────────────────────

def get_all_active_products() -> list:
    """
    Return all products where is_active=True.

    filter(is_active=True) uses the DB index we set on that field,
    so this query stays fast even with thousands of products.

    order_by("created_at") gives consistent ordering — without this,
    the database can return rows in any order, which causes unpredictable
    UI behavior (products jumping around between page loads).

    list() evaluates the queryset immediately — Django querysets are lazy,
    meaning the DB query doesn't run until you iterate or call list().
    """
    return list(Product.objects.filter(is_active=True).order_by("created_at"))


def get_product_by_id(product_id: str) -> Product:
    """
    Return a single product by its UUID string.

    We check is_active=True here too — inactive products are
    treated as non-existent from the API's perspective.
    A user should never be able to view or order an inactive product.

    Raises:
      ProductNotFoundError: if product doesn't exist or is inactive
    """
    try:
        return Product.objects.get(id=product_id, is_active=True)
    except ObjectDoesNotExist:
        raise ProductNotFoundError(f"Product {product_id} not found")


def update_stock(product_id: str, new_stock_count: int) -> Product:
    """
    Update the stock count for a product.
    Called by the Order service after a successful checkout.

    Why transaction.atomic()?
      A database transaction groups operations so they either ALL succeed
      or ALL fail together. Nothing is left half-done if something crashes.

    Why select_for_update()?
      Imagine two users checkout simultaneously — both check stock, both
      see 1 unit available, both place orders. You've now oversold by 1.
      select_for_update() locks the product row the moment we read it.
      The second request has to WAIT until the first transaction finishes.
      This is called a pessimistic lock — assume conflict, prevent it upfront.

    select_for_update() REQUIRES being inside transaction.atomic().
    Without atomic(), Django has no transaction to attach the lock to,
    which is exactly the error you just saw.

    update_fields=["stock_count", "updated_at"] tells Django to only
    UPDATE those two columns instead of writing every field — more efficient
    and safer (avoids accidentally overwriting other fields).

    Raises:
      ProductNotFoundError: if product UUID doesn't exist
    """
    try:
        with transaction.atomic():
            # Lock this row — other requests wait here until we're done
            product = Product.objects.select_for_update().get(id=product_id)

            product.stock_count = new_stock_count

            # Only save the fields that changed — not the entire row
            product.save(update_fields=["stock_count", "updated_at"])

            return product
            # Lock is released here when the with block exits

    except Product.DoesNotExist:
        raise ProductNotFoundError(f"Product {product_id} not found")


def check_stock_available(product_id: str, quantity: int) -> Product:
    """
    Verify that enough stock exists before creating an order.
    Called by the Order service during checkout, before payment.

    If this passes, the Order service proceeds to payment.
    If this fails, checkout is blocked immediately — no point charging
    someone for a product we can't deliver.

    Raises:
      ProductNotFoundError: if product doesn't exist (via get_product_by_id)
      OutOfStockError: if available stock is less than requested quantity
    """
    product = get_product_by_id(product_id)

    if product.stock_count < quantity:
        raise OutOfStockError(
            f"Only {product.stock_count} units available, {quantity} requested"
        )

    return product