"""
FastAPI route handlers for auth endpoints.

Philosophy: routes are THIN.
  - Parse request → call service → return response
  - No business logic here
  - Catch service exceptions → convert to HTTP errors

The get_current_user dependency is the JWT guard.
Any route that uses it will automatically require a valid token.
"""

from fastapi import APIRouter, HTTPException, Depends, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .schemas import (
    RegisterRequest, RegisterResponse,
    LoginRequest, LoginResponse,
    RefreshRequest, RefreshResponse,
    LogoutRequest, MessageResponse,
    MeResponse, UserResponse, TokenResponse,
)
from .service import (
    register_user,
    login_user,
    refresh_access_token,
    logout_user,
    get_user_from_token,
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    AccountInactiveError,
    InvalidTokenError,
)

# APIRouter groups related endpoints together.
# We'll mount this onto the main FastAPI app with a prefix.
router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# HTTPBearer extracts the token from "Authorization: Bearer <token>" header
# auto_error=False means we handle the missing-token case ourselves
bearer_scheme = HTTPBearer(auto_error=False)


# ──────────────────────────────────────────────
# Dependency: JWT guard
# ──────────────────────────────────────────────

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    """
    FastAPI dependency — validates JWT and returns the current user.

    Usage in any protected route:
        @router.get("/me")
        def me(user = Depends(get_current_user)):
            ...

    FastAPI automatically:
      1. Extracts the Bearer token from the Authorization header
      2. Calls this function
      3. Injects the returned user into the route function
      4. Returns 401 automatically if this raises HTTPException
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing. Include: Authorization: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user = get_user_from_token(credentials.credentials)
        return user
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


# ──────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────

@router.post("/register", response_model=RegisterResponse, status_code=201)
def register(body: RegisterRequest):
    """
    Create a new user account.

    FastAPI automatically:
      - Parses the JSON body into RegisterRequest
      - Validates fields (email format, password strength)
      - Returns 422 with details if validation fails
    """
    try:
        user = register_user(
            first_name=body.first_name,
            last_name=body.last_name,
            email=body.email,
            password=body.password,
        )
        return RegisterResponse(
            data=UserResponse.model_validate(user),
            message="Account created successfully",
        )

    except EmailAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "EMAIL_TAKEN",
                    "message": "This email is already registered",
                }
            },
        )


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, request: Request):
    """
    Authenticate and receive access + refresh tokens.

    The refresh token is ALSO set as an httpOnly cookie.
    The access token is returned in the response body for the frontend to store in memory.
    """
    # Extract device info from User-Agent header for token tracking
    device_info = request.headers.get("User-Agent", "Unknown")[:255]

    try:
        tokens = login_user(
            email=body.email,
            password=body.password,
            device_info=device_info,
        )

        from fastapi.responses import JSONResponse
        response = JSONResponse(
            content={
                "data": {
                    "access_token": tokens["access_token"],
                    "token_type": "Bearer",
                    "expires_in": tokens["expires_in"],
                },
                "message": "Login successful",
            }
        )

        # Set refresh token as httpOnly cookie
        # httpOnly=True → JavaScript cannot access this cookie
        # secure=True → only sent over HTTPS (set False for local dev)
        # samesite="lax" → protection against CSRF attacks
        response.set_cookie(
            key="refresh_token",
            value=tokens["refresh_token"],
            httponly=True,
            secure=False,   # Change to True in production
            samesite="lax",
            max_age=604800, # 7 days in seconds
        )

        return response

    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "INVALID_CREDENTIALS",
                    "message": "Invalid email or password",
                }
            },
        )
    except AccountInactiveError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "ACCOUNT_INACTIVE",
                    "message": "This account has been suspended",
                }
            },
        )


@router.post("/refresh", response_model=RefreshResponse)
def refresh(request: Request):
    """
    Exchange a valid refresh token for a new access token.

    Reads the refresh token from the httpOnly cookie
    (not from the request body — the browser sends it automatically).
    """
    refresh_token_value = request.cookies.get("refresh_token")

    if not refresh_token_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "NO_REFRESH_TOKEN",
                    "message": "No refresh token found. Please log in.",
                }
            },
        )

    try:
        tokens = refresh_access_token(refresh_token_value)

        from fastapi.responses import JSONResponse
        response = JSONResponse(
            content={
                "data": {
                    "access_token": tokens["access_token"],
                    "token_type": "Bearer",
                    "expires_in": tokens["expires_in"],
                },
                "message": "Token refreshed",
            }
        )

        # Rotate the cookie too
        response.set_cookie(
            key="refresh_token",
            value=tokens["refresh_token"],
            httponly=True,
            secure=False,
            samesite="lax",
            max_age=604800,
        )

        return response

    except (InvalidTokenError, AccountInactiveError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_TOKEN", "message": str(e)}},
        )


@router.post("/logout", response_model=MessageResponse)
def logout(request: Request):
    """
    Revoke the refresh token and clear the cookie.

    The access token expires naturally — nothing to do there.
    """
    refresh_token_value = request.cookies.get("refresh_token")

    if refresh_token_value:
        logout_user(refresh_token_value)

    from fastapi.responses import JSONResponse
    response = JSONResponse(content={"message": "Logged out successfully"})

    # Clear the cookie from the browser
    response.delete_cookie(key="refresh_token")

    return response


@router.get("/me", response_model=MeResponse)
def me(current_user=Depends(get_current_user)):
    """
    Return the currently authenticated user's profile.

    Depends(get_current_user) is the JWT guard.
    FastAPI calls get_current_user first, and if it raises,
    this function never runs — 401 is returned automatically.
    """
    return MeResponse(
        data=UserResponse.model_validate(current_user),
        message="User profile fetched",
    )