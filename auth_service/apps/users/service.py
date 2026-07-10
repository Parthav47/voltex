"""
Service layer — business logic for auth operations.

Rules for this file:
  - No FastAPI imports (no Request, Response, HTTPException)
  - No Pydantic schemas
  - Only Django ORM + security.py
  - Functions raise plain Python exceptions with clear messages
  - Routes catch those exceptions and convert them to HTTP responses

Why this separation?
  If tomorrow you want to write unit tests, you can test register_user()
  without starting an HTTP server. That's the power of this pattern.
"""

import os
from datetime import datetime, timezone, timedelta

from django.core.exceptions import ObjectDoesNotExist
from jose import JWTError

from .models import User, RefreshToken
from .security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token_value,
    decode_access_token,
    REFRESH_TOKEN_EXPIRE_SECONDS,
    ACCESS_TOKEN_EXPIRE_SECONDS,
)


# ──────────────────────────────────────────────
# Custom exceptions — raised by service, caught by routes
# ──────────────────────────────────────────────

class EmailAlreadyExistsError(Exception):
    pass

class InvalidCredentialsError(Exception):
    pass

class AccountInactiveError(Exception):
    pass

class InvalidTokenError(Exception):
    pass


# ──────────────────────────────────────────────
# Service functions
# ──────────────────────────────────────────────

def register_user(first_name: str, last_name: str, email: str, password: str) -> User:
    """
    Create a new user account.

    Steps:
      1. Check if email is already taken
      2. Hash the password
      3. Save the user to DB
      4. Return the user object

    Raises:
      EmailAlreadyExistsError: if email is already registered
    """
    # Case-insensitive email check
    email = email.lower().strip()

    if User.objects.filter(email=email).exists():
        raise EmailAlreadyExistsError(f"Email '{email}' is already registered")

    # Hash BEFORE saving — never save plain passwords
    password_hash = hash_password(password)

    user = User.objects.create(
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        email=email,
        password_hash=password_hash,
        is_active=True,
    )

    return user


def login_user(email: str, password: str, device_info: str = None) -> dict:
    """
    Authenticate a user and return access + refresh tokens.

    Steps:
      1. Look up user by email
      2. Verify password against stored hash
      3. Check account is active
      4. Create access token (JWT)
      5. Create refresh token (random UUID, stored in DB)
      6. Return both tokens

    Raises:
      InvalidCredentialsError: if email not found or password wrong
        (we give the SAME error for both — don't tell attackers which one failed)
      AccountInactiveError: if account is suspended
    """
    email = email.lower().strip()

    # Try to find the user
    try:
        user = User.objects.get(email=email)
    except ObjectDoesNotExist:
        # Same error as wrong password — don't leak whether email exists
        raise InvalidCredentialsError("Invalid email or password")

    # Verify password
    if not verify_password(password, user.password_hash):
        raise InvalidCredentialsError("Invalid email or password")

    # Check account is active
    if not user.is_active:
        raise AccountInactiveError("This account has been suspended")

    # Create access token
    access_token = create_access_token(str(user.id), user.email)

    # Create refresh token and persist it
    refresh_token_value = create_refresh_token_value()
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=REFRESH_TOKEN_EXPIRE_SECONDS)

    RefreshToken.objects.create(
        user=user,
        token=refresh_token_value,
        device_info=device_info,
        expires_at=expires_at,
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token_value,
        "expires_in": ACCESS_TOKEN_EXPIRE_SECONDS,
    }


def refresh_access_token(refresh_token_value: str) -> dict:
    """
    Exchange a valid refresh token for a new access token.

    We also ROTATE the refresh token — the old one is deleted,
    a new one is created. This limits the damage if a refresh
    token is stolen: it can only be used once.

    Raises:
      InvalidTokenError: if token not found, expired, or already used
    """
    now = datetime.now(timezone.utc)

    try:
        # Look up the token in DB
        token_obj = RefreshToken.objects.select_related("user").get(
            token=refresh_token_value
        )
    except ObjectDoesNotExist:
        raise InvalidTokenError("Refresh token not found or already used")

    # Check expiry
    if token_obj.expires_at <= now:
        # Clean up expired token
        token_obj.delete()
        raise InvalidTokenError("Refresh token has expired. Please log in again.")

    # Check user is still active
    if not token_obj.user.is_active:
        raise AccountInactiveError("This account has been suspended")

    user = token_obj.user

    # ROTATE: delete old token, create new one
    token_obj.delete()

    new_access_token = create_access_token(str(user.id), user.email)
    new_refresh_value = create_refresh_token_value()
    new_expires_at = now + timedelta(seconds=REFRESH_TOKEN_EXPIRE_SECONDS)

    RefreshToken.objects.create(
        user=user,
        token=new_refresh_value,
        device_info=token_obj.device_info,  # preserve device info
        expires_at=new_expires_at,
    )

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_value,
        "expires_in": ACCESS_TOKEN_EXPIRE_SECONDS,
    }


def logout_user(refresh_token_value: str) -> None:
    """
    Revoke a refresh token (log out).

    Simply deletes the refresh token from the DB.
    The access token will expire naturally within 15 minutes.
    We don't need to do anything about the access token.

    If the token doesn't exist, we silently succeed —
    idempotent logout is better UX than an error.
    """
    RefreshToken.objects.filter(token=refresh_token_value).delete()


def get_user_from_token(token: str) -> User:
    """
    Validate a JWT access token and return the corresponding User.

    Used by the get_current_user dependency in routes.py.

    Raises:
      InvalidTokenError: if token is invalid or expired
      InvalidTokenError: if user no longer exists
    """
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")

        if not user_id:
            raise InvalidTokenError("Token payload missing user ID")

    except JWTError:
        raise InvalidTokenError("Invalid or expired access token")

    try:
        user = User.objects.get(id=user_id, is_active=True)
    except ObjectDoesNotExist:
        raise InvalidTokenError("User not found or inactive")

    return user