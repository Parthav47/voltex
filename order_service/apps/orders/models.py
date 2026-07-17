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
      COD:    pending → confirmed → shipped → delivered
      Online: pending → paid → shipped → delivered
      Either: pending → failed (payment failed)
              pending → cancelled (user cancelled before payment)

    payment_method determines which lifecycle applies.
    COD skips the payment step entirely — goes straight to confirmed.
    """

    # ──────────────────────────────────────────────
    # Status constants — use these instead of raw strings
    # e.g. Order.STATUS_PAID not "paid" — prevents typos
    # ──────────────────────────────────────────────
    STATUS_PENDING = "pending"
    STATUS_CONFIRMED = "confirmed"   # COD only — order confirmed, awaiting shipment
    STATUS_PAID = "paid"             # Online only — payment captured by Razorpay
    STATUS_SHIPPED = "shipped"
    STATUS_DELIVERED = "delivered"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_PAID, "Paid"),
        (STATUS_SHIPPED, "Shipped"),
        (STATUS_DELIVERED, "Delivered"),
        (STATUS_FAILED, "Failed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    # ──────────────────────────────────────────────
    # Payment method constants
    # ──────────────────────────────────────────────
    PAYMENT_COD = "cod"
    PAYMENT_ONLINE = "online"

    PAYMENT_METHOD_CHOICES = [
        (PAYMENT_COD, "Cash on Delivery"),
        (PAYMENT_ONLINE, "Online"),
    ]

    # ──────────────────────────────────────────────
    # Core fields
    # ──────────────────────────────────────────────
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # No ForeignKey — User lives in auth_service DB, not here.
    # We trust the JWT to give us user_id. No cross-service DB join.
    user_id = models.UUIDField(db_index=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,  # indexed — we filter orders by status frequently
    )

    # Which payment method the user chose at checkout.
    # Determines the status lifecycle and whether Payment service is called.
    payment_method = models.CharField(
        max_length=10,
        choices=PAYMENT_METHOD_CHOICES,
        default=PAYMENT_ONLINE,
    )

    # ──────────────────────────────────────────────
    # Financial fields
    # ──────────────────────────────────────────────

    # Frozen at checkout — never recalculated.
    # If the product price changes tomorrow, this order still
    # reflects what the customer actually agreed to pay.
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    # ──────────────────────────────────────────────
    # Shipping address — frozen snapshot at checkout time
    # ──────────────────────────────────────────────
    # Stored directly on the order, not as a FK to a user address.
    # Why? Users can update their address later — but this order
    # must permanently record WHERE it was supposed to be delivered.
    # Denormalization is intentional and correct here.
    shipping_name = models.CharField(max_length=255)
    shipping_address_line1 = models.CharField(max_length=255)
    shipping_address_line2 = models.CharField(max_length=255, blank=True, default="")
    shipping_city = models.CharField(max_length=100)
    shipping_state = models.CharField(max_length=100)
    shipping_pincode = models.CharField(max_length=10)
    shipping_phone = models.CharField(max_length=15)

    # ──────────────────────────────────────────────
    # Timestamps
    # ──────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)  # set once on creation
    updated_at = models.DateTimeField(auto_now=True)       # updated on every .save()

    class Meta:
        db_table = "orders"

    def __str__(self):
        return f"Order {self.id} — {self.status} ({self.payment_method})"


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