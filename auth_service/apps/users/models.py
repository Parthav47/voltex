"""
Database models for the Auth service.

These classes map directly to PostgreSQL tables.
Django reads these and creates the actual SQL tables via migrations.

Key decisions explained:
  - UUIDs as primary keys: harder to guess than integers (security)
  - is_active flag: soft-disable accounts without deleting rows
  - password_hash: never store plain text passwords, ever
"""

import uuid
from django.db import models


class User(models.Model):
    """
    Represents a registered user.

    Django will create a table named: apps_users_user
    (app_label + model_name, lowercased)

    We override this to just "users" using Meta.db_table.
    """

    # UUIDField auto-generates a unique ID for every new row
    # primary_key=True replaces Django's default integer "id"
    # editable=False means it can't be changed after creation
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)

    # unique=True means no two users can have the same email
    # Django automatically creates a DB index on unique fields
    email = models.EmailField(unique=True)

    # We NEVER store the plain password.
    # This column stores the bcrypt hash (always 60 chars).
    password_hash = models.CharField(max_length=255)

    # Soft-delete/suspend flag.
    # Default True = active. Set False to block login without deleting the user.
    is_active = models.BooleanField(default=True)

    # auto_now_add=True: set automatically when the row is first created
    created_at = models.DateTimeField(auto_now_add=True)

    # auto_now=True: updated automatically every time .save() is called
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Override the default table name to something clean
        db_table = "users"

    def __str__(self):
        # This controls how the object prints in logs/debugger
        return f"{self.email} ({self.id})"


class RefreshToken(models.Model):
    """
    Stores active refresh tokens.

    Why store refresh tokens but not access tokens?
    - Access tokens are verified by signature alone (stateless) — no DB needed
    - Refresh tokens need to be revocable (logout) — so we store them

    When a user logs out, we DELETE their refresh token row.
    When they use /refresh, we look up the token, validate it, then
    ROTATE it (delete old, create new) for extra security.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # ForeignKey links each refresh token to a user.
    # on_delete=CASCADE: if the user is deleted, their tokens are deleted too.
    # db_index=True: adds a DB index so lookups by user_id are fast.
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="refresh_tokens",
        db_index=True
    )

    # The actual token string (a random UUID we generate)
    # unique=True: no two rows can have the same token value
    token = models.CharField(max_length=255, unique=True)

    # Which browser/device issued this token.
    # Useful for "log out of all devices" feature later.
    # blank=True means it's optional at the application level
    # null=True means the DB column can be NULL
    device_info = models.CharField(max_length=255, blank=True, null=True)

    # When this token stops working, regardless of DB presence
    expires_at = models.DateTimeField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "refresh_tokens"

    def __str__(self):
        return f"RefreshToken for user {self.user_id}"