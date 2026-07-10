"""
Product service HTTP client.

This file handles all HTTP communication with the Product service.
It's separate from service.py because:
  - service.py should not know HOW to make HTTP calls
  - If Product service URL changes, only this file changes
  - Easy to mock in tests — replace this with a fake that returns test data

This pattern is called an HTTP client or gateway layer.
"""

import os
import httpx
from dotenv import load_dotenv

load_dotenv()

PRODUCT_SERVICE_URL = os.environ.get("PRODUCT_SERVICE_URL", "http://localhost:8002")
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "")

# Timeout in seconds — don't wait forever if Product service is down
TIMEOUT = 10.0


class ProductServiceError(Exception):
    """Raised when Product service returns an error or is unreachable."""
    pass


def get_product(product_id: str) -> dict:
    """
    Fetch a single product from Product service.

    Returns the product data as a dict.
    Raises ProductServiceError if product not found or service is down.

    This is a synchronous HTTP call — Order service WAITS for the response
    before continuing. This is fine for checkout — we need the product
    data before we can proceed.
    """
    try:
        response = httpx.get(
            f"{PRODUCT_SERVICE_URL}/api/products/{product_id}",
            timeout=TIMEOUT,
        )

        if response.status_code == 404:
            raise ProductServiceError(f"Product {product_id} not found")

        if response.status_code != 200:
            raise ProductServiceError(
                f"Product service error: {response.status_code}"
            )

        # Response shape: {"data": {...product fields...}, "message": "..."}
        return response.json()["data"]

    except httpx.TimeoutException:
        raise ProductServiceError("Product service timed out")
    except httpx.ConnectError:
        raise ProductServiceError("Cannot connect to Product service")


def decrement_stock(product_id: str, new_stock_count: int) -> None:
    """
    Update stock count in Product service after successful checkout.

    Sends the X-Internal-Key header — required by Product service's
    PATCH /stock endpoint. Without it, Product service returns 403.

    This is fire-and-forget in terms of business logic — if this fails,
    we log it but don't fail the order (payment already succeeded).
    In production you'd have a retry mechanism or dead letter queue.
    """
    try:
        response = httpx.patch(
            f"{PRODUCT_SERVICE_URL}/api/products/{product_id}/stock",
            json={"stock_count": new_stock_count},
            headers={"X-Internal-Key": INTERNAL_API_KEY},
            timeout=TIMEOUT,
        )

        if response.status_code != 200:
            # Log but don't raise — order is already confirmed
            print(f"WARNING: Failed to update stock for {product_id}: {response.status_code}")

    except (httpx.TimeoutException, httpx.ConnectError) as e:
        print(f"WARNING: Could not reach Product service to update stock: {e}")