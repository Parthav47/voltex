"""
Pydantic schemas — request and response shapes.

What is Pydantic?
  Pydantic is a data validation library. You define the expected shape
  of data as a Python class, and Pydantic automatically:
    - Validates incoming data (correct types, required fields)
    - Returns clear error messages for invalid data
    - Serializes outgoing data (converts Python objects to JSON)

FastAPI uses Pydantic schemas as:
  - Request bodies (what the client sends)
  - Response models (what we send back)

Why separate from models.py?
  models.py = database shape (Django ORM)
  schemas.py = API shape (what HTTP clients see)
  These are intentionally different. You never expose your DB model directly.
"""

from pydantic import BaseModel, EmailStr, field_validator
from datetime import datetime
from uuid import UUID


# ──────────────────────────────────────────────
# Request schemas (what the client sends TO us)
# ──────────────────────────────────────────────

class RegisterRequest(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr          # Pydantic validates email format automatically
    password: str

    # Custom validators run after type checking
    @field_validator("password")
    @classmethod
    def password_must_be_strong(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if len(v) > 72:
            raise ValueError("Password must be less than 72 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one number")
        return v

    @field_validator("first_name", "last_name")
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name cannot be empty")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


# ──────────────────────────────────────────────
# Response schemas (what we send BACK to client)
# ──────────────────────────────────────────────

class UserResponse(BaseModel):
    """
    Safe user data to return in API responses.

    Notice: NO password_hash field.
    This is intentional — you never send the hash to the client.
    Pydantic only serializes fields defined here, so even if we
    accidentally pass a full Django model object, the hash won't leak.
    """
    id: UUID
    first_name: str
    last_name: str
    email: str
    is_active: bool
    created_at: datetime

    # This tells Pydantic it can read from Django ORM model attributes
    # (not just plain dicts)
    model_config = {"from_attributes": True}


class RegisterResponse(BaseModel):
    data: UserResponse
    message: str


class TokenResponse(BaseModel):
    """Returned after a successful login."""
    access_token: str
    token_type: str = "Bearer"
    expires_in: int          # seconds until access token expires


class LoginResponse(BaseModel):
    data: TokenResponse
    message: str


class RefreshResponse(BaseModel):
    data: TokenResponse
    message: str


class MeResponse(BaseModel):
    data: UserResponse
    message: str


class MessageResponse(BaseModel):
    """Generic response for actions that don't return data (logout, etc.)"""
    message: str


# ──────────────────────────────────────────────
# Error schema (consistent error shape)
# ──────────────────────────────────────────────

class ErrorDetail(BaseModel):
    code: str       # machine-readable: "EMAIL_TAKEN", "INVALID_CREDENTIALS"
    message: str    # human-readable: "This email is already registered"


class ErrorResponse(BaseModel):
    error: ErrorDetail