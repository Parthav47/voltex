"""
auth_client.py

Fetches user info from Auth service.
Used by Order service to get user email for notifications.
"""

import os
import httpx
from dotenv import load_dotenv

load_dotenv()

AUTH_SERVICE_URL = os.environ.get("AUTH_SERVICE_URL", "http://localhost:8001")
TIMEOUT = 5.0


class AuthServiceError(Exception):
    pass


def get_user_by_id(user_id: str, access_token: str) -> dict:
    """
    Fetch user profile from Auth service.
    Requires a valid JWT — pass the one from the current request.
    """
    try:
        response = httpx.get(
            f"{AUTH_SERVICE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=TIMEOUT,
        )
        if response.status_code == 200:
            return response.data.json()["data"]
        return {"first_name": "Customer", "email": ""}
    except Exception:
        return {"first_name": "Customer", "email": ""}