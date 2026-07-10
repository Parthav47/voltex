"""
Product model.

One table — products. That's all this service owns.

New concepts vs Auth service:
  - DecimalField for price (never use FloatField for money — floating
    point math is imprecise. DecimalField stores exact values.)
  - JSONField for images (a list of URL strings — no separate images table needed)
  - db_index=True on is_active — speeds up filtering active products
    when you have thousands of rows
"""

import uuid
from django.db import models


class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=255)

    # SKU = Stock Keeping Unit — unique product code e.g. "PBUD-X1-BLK"
    # Used by Order service to snapshot what was ordered at purchase time
    sku = models.CharField(max_length=100, unique=True)

    description = models.TextField(blank=True, default="")

    # DecimalField(max_digits=10, decimal_places=2) stores up to 99999999.99
    # NEVER use FloatField for money — 0.1 + 0.2 = 0.30000000000000004 in float
    price = models.DecimalField(max_digits=10, decimal_places=2)

    # How many units are available to purchase
    # Order service decrements this on successful checkout
    stock_count = models.PositiveIntegerField(default=0)

    # Soft-unpublish a product without deleting it
    # db_index=True because we filter by this on every product list call
    is_active = models.BooleanField(default=True, db_index=True)

    # JSON list of image URLs — ["https://cdn.../img1.jpg", "https://cdn.../img2.jpg"]
    # No separate images table needed for a single-product store
    images = models.JSONField(default=list, blank=True)

    # Shipping fields — needed for delivery calculation later
    weight_grams = models.PositiveIntegerField(default=0)
    dimensions = models.CharField(max_length=100, blank=True, default="")

    # SEO fields — for search engine indexing
    meta_title = models.CharField(max_length=255, blank=True, default="")
    meta_description = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "products"

    def __str__(self):
        return f"{self.name} ({self.sku})"