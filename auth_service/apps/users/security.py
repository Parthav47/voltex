"""
security.py — password hashing and JWT operations.

WHAT CHANGED AND WHY:
  We removed passlib entirely. passlib is a wrapper library around bcrypt
  that has a known bug with bcrypt versions 4.1+ — it runs an internal test
  using a password longer than 72 bytes, which newer bcrypt rejects with
  ValueError. So we now use bcrypt directly — fewer dependencies, same result.
"""

import os
import uuid
from datetime import datetime, timezone, timedelta

# bcrypt — industry standard password hashing library
# We use it directly instead of through passlib
import bcrypt

# jose — JSON Web Token library
# JWTError is raised when a token is invalid/expired/tampered
from jose import JWTError, jwt

from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────────
# Configuration — read from .env file
# ──────────────────────────────────────────────

# SECRET_KEY signs every JWT. If this leaks, anyone can forge tokens.
# Never hardcode this. Always read from environment variable.
SECRET_KEY = os.environ.get("SECRET_KEY", "fallback-dev-key-change-in-production")

# HS256 = HMAC with SHA-256
# Symmetric algorithm — same key signs AND verifies
# Good for microservices where you control all services
ALGORITHM = "HS256"

# Token lifetimes read from .env
# ACCESS = short lived (15 min) — limits damage if stolen
# REFRESH = long lived (7 days) — stored in httpOnly cookie, not JS-accessible
ACCESS_TOKEN_EXPIRE_SECONDS = int(os.environ.get("ACCESS_TOKEN_EXPIRE_SECONDS", 900))
REFRESH_TOKEN_EXPIRE_SECONDS = int(os.environ.get("REFRESH_TOKEN_EXPIRE_SECONDS", 604800))


# ──────────────────────────────────────────────
# Password hashing — using bcrypt directly
# ──────────────────────────────────────────────

def hash_password(plain_password: str) -> str:
    """
    Convert a plain text password into a bcrypt hash for safe DB storage.

    How bcrypt works:
      1. Generates a random 'salt' (random bytes added to the password)
      2. Combines password + salt and runs an intentionally slow hash
      3. Returns a single string containing: algorithm + rounds + salt + hash
         Example: "$2b$12$xK9mN3q...38qP"

    rounds=12 means 2^12 = 4096 iterations — takes ~300ms
    This slowness is intentional — makes brute force attacks impractical.

    Why encode to bytes?
      bcrypt works on raw bytes, not Python strings.
      .encode("utf-8") converts the string to bytes.
      .decode("utf-8") converts the result back to a string for DB storage.
    """
    password_bytes = plain_password.encode("utf-8")  # "MyPass123!" → b"MyPass123!"
    salt = bcrypt.gensalt(rounds=12)                 # generate fresh random salt
    hashed = bcrypt.hashpw(password_bytes, salt)     # hash password + salt together
    return hashed.decode("utf-8")                    # store as string in DB


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Check if a plain password matches a stored bcrypt hash.

    How verification works:
      bcrypt extracts the salt from the stored hash string,
      re-hashes the attempt with that same salt,
      then compares the result to the stored hash.

      The plain password is NEVER recoverable from the hash.
      This is a one-way function — verification works without reversing.

    Returns True if match, False if not.
    Never raises an exception for wrong passwords — just returns False.
    """
    password_bytes = plain_password.encode("utf-8")
    hashed_bytes = hashed_password.encode("utf-8")  # DB string → bytes for bcrypt
    return bcrypt.checkpw(password_bytes, hashed_bytes)


# ──────────────────────────────────────────────
# JWT — JSON Web Tokens
# ──────────────────────────────────────────────

def create_access_token(user_id: str, email: str) -> str:
    """
    Create a short-lived signed JWT access token.

    JWT structure — three base64 parts joined by dots:
      Header.Payload.Signature
      eyJhbGc....eyJ1c2VyX2....SflKxwRJS

    Header: {"alg": "HS256", "typ": "JWT"}
    Payload (what we put in):
      - sub: subject — standard JWT claim, we store user_id here
      - email: included so other services can read it without a DB call
      - type: "access" — lets us reject refresh tokens used as access tokens
      - exp: expiry — jose enforces this automatically on decode

    Important: JWT payload is base64 encoded, NOT encrypted.
    Anyone can decode and read it. Never put passwords or card data in a JWT.
    The SIGNATURE proves it wasn't tampered with — that's the security.
    """
    expire = datetime.now(timezone.utc) + timedelta(seconds=ACCESS_TOKEN_EXPIRE_SECONDS)

    payload = {
        "sub": str(user_id),  # always convert UUID to string for JWT
        "email": email,
        "type": "access",     # guard against refresh tokens being used here
        "exp": expire,        # jose uses this to auto-reject expired tokens
    }

    # jwt.encode signs the payload with SECRET_KEY using HS256
    # Returns a string: "xxxxx.yyyyy.zzzzz"
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token_value() -> str:
    """
    Generate a random opaque string to use as a refresh token.

    This is NOT a JWT — it's just a random UUID stored in the database.

    Why not a JWT for refresh tokens?
      Refresh tokens need to be REVOCABLE (logout, stolen token).
      JWTs are stateless — you can't revoke them without a DB anyway.
      A plain random UUID stored in DB is simpler and equally secure.
      On logout we just delete the row. Clean and simple.
    """
    return str(uuid.uuid4())  # "a1b2c3d4-e5f6-..." random every time


def decode_access_token(token: str) -> dict:
    """
    Decode and validate a JWT access token.

    What jose checks automatically:
      - Signature valid (token wasn't tampered with)
      - Token not expired (exp claim)
      - Algorithm matches (prevents algorithm confusion attacks)

    We additionally check:
      - type == "access" (rejects refresh tokens used as access tokens)

    Raises JWTError if anything is wrong.
    The caller (get_user_from_token in service.py) catches this
    and raises InvalidTokenError, which routes.py converts to HTTP 401.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # Extra guard — reject if someone passes a refresh token here
        if payload.get("type") != "access":
            raise JWTError("Not an access token")

        return payload  # {"sub": "uuid", "email": "...", "type": "access", "exp": ...}

    except JWTError:
        raise  # re-raise so the caller can return 401 to the client