"""
Order service — business logic.

This is the most complex service.
It coordinates between Cart DB, Order DB, and Product service HTTP calls.

Key patterns used:
  - transaction.atomic() for checkout — multiple DB writes must succeed together
  - product_client for HTTP calls to Product service
  - Custom exceptions converted to HTTP errors in routes.py
"""

import httpx
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist

from .models import Cart, CartItem, Order, OrderItem
from .product_client import get_product, decrement_stock, ProductServiceError
import os
import httpx
from dotenv import load_dotenv
load_dotenv()


# ──────────────────────────────────────────────
# Custom exceptions
# ──────────────────────────────────────────────

class CartNotFoundError(Exception):
    pass

class CartItemNotFoundError(Exception):
    pass

class OrderNotFoundError(Exception):
    pass

class OrderAccessDeniedError(Exception):
    pass

class EmptyCartError(Exception):
    pass

class ProductUnavailableError(Exception):
    pass

class InsufficientStockError(Exception):
    pass


# ──────────────────────────────────────────────
# Cart operations
# ──────────────────────────────────────────────

def get_or_create_cart(user_id: str) -> Cart:
    """
    Get existing cart for user, or create one if none exists.
    get_or_create returns (object, created_bool) — we only need the object.
    """
    cart, _ = Cart.objects.get_or_create(user_id=user_id)
    return cart


def get_cart_with_items(user_id: str) -> dict:
    """
    Return cart with all items enriched with product data from Product service.

    This is where inter-service communication happens for reads.
    For each cart item, we call Product service to get current name and price.

    Why not store price in cart_items?
      Cart prices should reflect current pricing — if price changes while
      items are in cart, the user should see the updated price.
      Order prices are frozen at checkout — that's different.
    """
    cart = get_or_create_cart(user_id)
    items = list(cart.items.all())

    enriched_items = []
    total = Decimal("0.00")

    for item in items:
        try:
            # Call Product service for current name and price
            product = get_product(str(item.product_id))

            unit_price = Decimal(str(product["price"]))
            subtotal = unit_price * item.quantity
            total += subtotal

            enriched_items.append({
                "cart_item_id": item.id,
                "product_id": item.product_id,
                "product_name": product["name"],
                "unit_price": unit_price,
                "quantity": item.quantity,
                "subtotal": subtotal,
            })

        except ProductServiceError:
            # Product may have been deleted — skip it
            continue

    return {
        "cart_id": cart.id,
        "items": enriched_items,
        "total": total,
    }


def add_to_cart(user_id: str, product_id: str, quantity: int) -> CartItem:
    """
    Add a product to the user's cart.

    If item already exists, increment quantity.
    If item is new, create it.
    Validates stock with Product service before adding.
    """
    # Verify product exists and has enough stock
    try:
        product = get_product(product_id)
    except ProductServiceError as e:
        raise ProductUnavailableError(str(e))

    if product["stock_count"] < quantity:
        raise InsufficientStockError(
            f"Only {product['stock_count']} units available"
        )

    cart = get_or_create_cart(user_id)

    # update_or_create: update quantity if exists, create if not
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        product_id=product_id,
        defaults={"quantity": quantity},
    )

    if not created:
        # Item already in cart — add to existing quantity
        cart_item.quantity += quantity
        cart_item.save(update_fields=["quantity"])

    return cart_item


def update_cart_item(user_id: str, cart_item_id: str, quantity: int) -> CartItem:
    """
    Update quantity of a cart item.
    If quantity is 0, remove the item.
    """
    cart = get_or_create_cart(user_id)

    try:
        cart_item = CartItem.objects.get(id=cart_item_id, cart=cart)
    except ObjectDoesNotExist:
        raise CartItemNotFoundError("Cart item not found")

    if quantity == 0:
        cart_item.delete()
        return None

    cart_item.quantity = quantity
    cart_item.save(update_fields=["quantity"])
    return cart_item


def remove_cart_item(user_id: str, cart_item_id: str) -> None:
    """Remove a specific item from the cart."""
    cart = get_or_create_cart(user_id)

    try:
        cart_item = CartItem.objects.get(id=cart_item_id, cart=cart)
        cart_item.delete()
    except ObjectDoesNotExist:
        raise CartItemNotFoundError("Cart item not found")


# ──────────────────────────────────────────────
# Checkout
# ──────────────────────────────────────────────

def checkout(user_id: str, shipping_data: dict) -> dict:
    """
    Convert a cart into a confirmed order.

    This is the most critical function in the entire system.
    It must be atomic — either everything succeeds or nothing does.

    Steps inside the transaction:
      1. Get cart and verify it has items
      2. Fetch current product data from Product service
      3. Verify stock is still available
      4. Create Order row with shipping address
      5. Create OrderItem rows with snapshot data
      6. Delete the cart (it's been converted)

    After the transaction:
      7. Call Payment service to create Razorpay order
         (outside transaction — payment is external, can't roll it back)

    Returns razorpay_order_id for frontend to open payment popup.
    """
    cart = get_or_create_cart(user_id)
    items = list(cart.items.all())

    if not items:
        raise EmptyCartError("Cannot checkout with an empty cart")

    # Fetch all product data before starting transaction
    # We do this OUTSIDE the transaction to keep the transaction short
    # Long transactions holding DB locks cause performance problems
    product_data = {}
    for item in items:
        try:
            product = get_product(str(item.product_id))
            product_data[str(item.product_id)] = product
        except ProductServiceError as e:
            raise ProductUnavailableError(f"Product unavailable: {e}")

    # Verify stock for all items before creating order
    for item in items:
        product = product_data[str(item.product_id)]
        if product["stock_count"] < item.quantity:
            raise InsufficientStockError(
                f"'{product['name']}': only {product['stock_count']} units available"
            )

    # Calculate total
    total_amount = sum(
        Decimal(str(product_data[str(item.product_id)]["price"])) * item.quantity
        for item in items
    )

    # Create order atomically — all or nothing
    with transaction.atomic():
        order = Order.objects.create(
            user_id=user_id,
            status=Order.STATUS_PENDING,
            total_amount=total_amount,
            **shipping_data,  # unpack all shipping fields
        )

        # Create order items with snapshot data
        for item in items:
            product = product_data[str(item.product_id)]
            OrderItem.objects.create(
                order=order,
                product_id=item.product_id,
                product_name=product["name"],     # snapshot
                product_sku=product["sku"],        # snapshot
                quantity=item.quantity,
                unit_price=Decimal(str(product["price"])),  # snapshot
            )

        # Delete cart — it's been converted to an order
        cart.delete()

    # Update stock in Product service — outside transaction
    for item in items:
        product = product_data[str(item.product_id)]
        new_stock = product["stock_count"] - item.quantity
        decrement_stock(str(item.product_id), new_stock)

        # Call Payment service to create Razorpay order
    PAYMENT_SERVICE_URL = os.environ.get("PAYMENT_SERVICE_URL", "http://localhost:8004")
    INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "")

    try:
        response = httpx.post(
            f"{PAYMENT_SERVICE_URL}/api/payments/initiate",
            json={
                "order_id": str(order.id),
                "amount": str(total_amount),
                "currency": "INR",
            },
            headers={"X-Internal-Key": INTERNAL_API_KEY},
            timeout=10.0,
        )
        payment_data = response.json()["data"]
        razorpay_order_id = payment_data["razorpay_order_id"]
    except Exception as e:
        # Payment initiation failed — order exists but payment not started
        # Frontend can retry payment using the order_id
        razorpay_order_id = None
        print(f"WARNING: Payment initiation failed: {e}")

    return {
        "order_id": str(order.id),
        "status": order.status,
        "total_amount": str(total_amount),
        "razorpay_order_id": razorpay_order_id,
    }


# ──────────────────────────────────────────────
# Order retrieval
# ──────────────────────────────────────────────

def get_user_orders(user_id: str) -> list:
    """Return all orders for a user, newest first."""
    return list(
        Order.objects.filter(user_id=user_id).order_by("-created_at")
    )


def get_order_detail(user_id: str, order_id: str) -> Order:
    """
    Return full order detail.
    Verifies the order belongs to the requesting user.
    A user must never see another user's order — hence the user_id check.
    """
    try:
        order = Order.objects.prefetch_related("items").get(id=order_id)
    except ObjectDoesNotExist:
        raise OrderNotFoundError("Order not found")

    # Authorization check — does this order belong to this user?
    if str(order.user_id) != str(user_id):
        raise OrderAccessDeniedError("You don't have access to this order")

    return order


def update_order_status(order_id: str, new_status: str) -> Order:
    """
    Update order status.
    Called internally when Payment service webhook confirms payment.
    """
    try:
        order = Order.objects.get(id=order_id)
        order.status = new_status
        order.save(update_fields=["status", "updated_at"])
        return order
    except ObjectDoesNotExist:
        raise OrderNotFoundError(f"Order {order_id} not found")