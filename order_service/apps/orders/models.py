"""
Order service models — Cart, CartItem, Order, OrderItem.

Key design decisions:
  - user_id is stored as a plain UUIDField, NOT a ForeignKey.
    There is no users table in this database — it lives in auth_service.
    This is the database-per-service pattern in action.
    We trust the JWT to give us the user_id — no DB join needed.

  - order_items store product_name and product_sku as snapshot fields.
    If the product name changes later, old orders still show the original name.
    This is called denormalization — intentionally duplicating data for
    correctness across time.

  - Cart is separate from Order intentionally.
    A cart is temporary (abandoned carts are common).
    An order is permanent (created only at checkout).
"""

import uuid
from django.db import models


class Cart(models.Model):
    """
    Temporary shopping cart — one per user.
    Created when user adds first item, deleted after successful checkout.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # No ForeignKey — user lives in a different service/database
    user_id = models.UUIDField(db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "carts"

    def __str__(self):
        return f"Cart {self.id} for user {self.user_id}"


class CartItem(models.Model):
    """
    A single product line in a cart.
    Deleted when item is removed or cart is converted to order.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")

    # product_id references Product service — no ForeignKey across services
    product_id = models.UUIDField()

    quantity = models.PositiveIntegerField(default=1)

    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cart_items"
        # One product per cart — prevent duplicate rows for same product
        unique_together = [["cart", "product_id"]]


class Order(models.Model):
    """
    A confirmed purchase — created at checkout, permanent record.

    Status lifecycle:
      pending → paid → shipped → delivered
      pending → failed (payment failed)
      pending → cancelled (user cancelled before payment)
    """

    # All valid status values — using constants prevents typos in code
    STATUS_PENDING = "pending"
    STATUS_PAID = "paid"
    STATUS_SHIPPED = "shipped"
    STATUS_DELIVERED = "delivered"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PAID, "Paid"),
        (STATUS_SHIPPED, "Shipped"),
        (STATUS_DELIVERED, "Delivered"),
        (STATUS_FAILED, "Failed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.UUIDField(db_index=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,   # index because we filter by status frequently
    )

    # Total frozen at checkout time — not recalculated later
    # Protects against price changes affecting historical orders
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    # Shipping address — frozen at checkout time
    # Stored on the order directly, not referenced from a user profile
    # Because users can change their address but orders must remember where they shipped
    shipping_name = models.CharField(max_length=255)
    shipping_address_line1 = models.CharField(max_length=255)
    shipping_address_line2 = models.CharField(max_length=255, blank=True, default="")
    shipping_city = models.CharField(max_length=100)
    shipping_state = models.CharField(max_length=100)
    shipping_pincode = models.CharField(max_length=10)
    shipping_phone = models.CharField(max_length=15)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "orders"

    def __str__(self):
        return f"Order {self.id} — {self.status}"


class OrderItem(models.Model):
    """
    A single product line in a confirmed order.

    product_name and product_sku are snapshot fields — they copy the
    product's name and SKU at the moment of purchase.

    Why snapshot?
      Without snapshots: if "ProBuds X1" is renamed to "ProBuds Pro",
      your order history shows the new name — confusing and legally wrong.
      With snapshots: order history always shows what was actually ordered.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")

    product_id = models.UUIDField()

    # Snapshot fields — frozen at purchase time
    product_name = models.CharField(max_length=255)
    product_sku = models.CharField(max_length=100)

    quantity = models.PositiveIntegerField()

    # Price per unit at time of purchase — not the current price
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = "order_items"