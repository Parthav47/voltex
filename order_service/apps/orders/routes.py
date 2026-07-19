"""
Order service routes.

Protected routes use the same JWT pattern as Auth service —
we extract user_id from the token without calling Auth service.
The JWT signature proves it's valid. No inter-service call needed.
"""

import os
from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from dotenv import load_dotenv

from .schemas import (
    AddToCartRequest, UpdateCartItemRequest, CheckoutRequest,
    CartEnvelope, AddToCartEnvelope, CheckoutEnvelope,
    OrderEnvelope, OrderListEnvelope, MessageResponse,
    CartItemResponse, CartResponse, OrderItemResponse,
    ShippingAddressResponse, OrderResponse, OrderListItemResponse,
)
from .service import (
    get_cart_with_items, add_to_cart, update_cart_item, remove_cart_item,
    checkout, get_user_orders, get_order_detail,
    CartItemNotFoundError, OrderNotFoundError, OrderAccessDeniedError,
    EmptyCartError, ProductUnavailableError, InsufficientStockError,
)

load_dotenv()

router = APIRouter(prefix="/api/orders", tags=["Orders"])
bearer_scheme = HTTPBearer(auto_error=False)

# Must match Auth service SECRET_KEY — so we can verify JWTs independently
# Both services share the same secret, so Order service verifies tokens
# without calling Auth service on every request
SECRET_KEY = os.environ.get("SECRET_KEY", "fallback-dev-key-change-in-production")
ALGORITHM = "HS256"


# ──────────────────────────────────────────────
# JWT dependency — same logic as Auth service
# ──────────────────────────────────────────────

    
def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    
    """
    Extract and verify user_id from JWT.

    Key insight: we verify the token using SECRET_KEY directly.
    We do NOT call Auth service — that would add latency on every request.
    Since both services share SECRET_KEY, we can verify independently.
    This is why JWT is perfect for microservices.

    Returns both user_id and email from JWT payload.
    Email is embedded in the token — no Auth service call needed.
    """
    
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_TOKEN", "message": "Authorization header missing"}},
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        email = payload.get("email", "")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"user_id": user_id, "email": email}
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_TOKEN", "message": "Invalid or expired token"}},
        )


# ──────────────────────────────────────────────
# Cart routes
# ──────────────────────────────────────────────

@router.get("/cart", response_model=CartEnvelope)
def get_cart(user_info: dict = Depends(get_current_user_id)):
    user_id = user_info["user_id"]
    cart_data = get_cart_with_items(user_id)
    return CartEnvelope(
        data=CartResponse(
            cart_id=cart_data["cart_id"],
            items=[CartItemResponse(**item) for item in cart_data["items"]],
            total=cart_data["total"],
        ),
        message="Cart retrieved",
    )


@router.post("/cart/items", response_model=AddToCartEnvelope, status_code=201)
def add_item_to_cart(
    body: AddToCartRequest,
    user_info: dict = Depends(get_current_user_id),
):
    user_id = user_info["user_id"]
    #user_email = user_info["email"]
    try:
        cart_item = add_to_cart(user_id, str(body.product_id), body.quantity)
        return AddToCartEnvelope(
            data={"cart_item_id": str(cart_item.id)},
            message="Item added to cart",
        )
    except ProductUnavailableError as e:
        raise HTTPException(status_code=404, detail={"error": {"code": "PRODUCT_UNAVAILABLE", "message": str(e)}})
    except InsufficientStockError as e:
        raise HTTPException(status_code=400, detail={"error": {"code": "INSUFFICIENT_STOCK", "message": str(e)}})


@router.patch("/cart/items/{item_id}", response_model=MessageResponse)
def update_item_quantity(
    item_id: UUID,
    body: UpdateCartItemRequest,
    user_info: dict = Depends(get_current_user_id),
):
    user_id = user_info["user_id"]
    try:
        update_cart_item(user_id, str(item_id), body.quantity)
        return MessageResponse(message="Cart item updated")
    except CartItemNotFoundError as e:
        raise HTTPException(status_code=404, detail={"error": {"code": "ITEM_NOT_FOUND", "message": str(e)}})


@router.delete("/cart/items/{item_id}", response_model=MessageResponse)
def remove_item_from_cart(
    item_id: UUID,
    user_info: dict = Depends(get_current_user_id),
):
    user_id = user_info["user_id"]
    try:
        remove_cart_item(user_id, str(item_id))
        return MessageResponse(message="Item removed from cart")
    except CartItemNotFoundError as e:
        raise HTTPException(status_code=404, detail={"error": {"code": "ITEM_NOT_FOUND", "message": str(e)}})


# ──────────────────────────────────────────────
# Checkout
# ──────────────────────────────────────────────

@router.post("/checkout", response_model=CheckoutEnvelope, status_code=201)
def checkout_order(
    body: CheckoutRequest,
    user_info: dict = Depends(get_current_user_id),
):
    user_id = user_info["user_id"]
    user_email = user_info["email"]
    user_name = body.shipping_name  # use shipping name as the display name

    shipping_data = {
        "shipping_name": body.shipping_name,
        "shipping_address_line1": body.shipping_address_line1,
        "shipping_address_line2": body.shipping_address_line2,
        "shipping_city": body.shipping_city,
        "shipping_state": body.shipping_state,
        "shipping_pincode": body.shipping_pincode,
        "shipping_phone": body.shipping_phone,
    }

    try:
        result = checkout(
            user_id,
            shipping_data,
            body.payment_method,
            user_email=user_email,
            user_name=user_name,
        )
        return CheckoutEnvelope(
            data=result,
            message="Order created successfully.",
        )
    except EmptyCartError as e:
        raise HTTPException(status_code=400, detail={"error": {"code": "EMPTY_CART", "message": str(e)}})
    except ProductUnavailableError as e:
        raise HTTPException(status_code=400, detail={"error": {"code": "PRODUCT_UNAVAILABLE", "message": str(e)}})
    except InsufficientStockError as e:
        raise HTTPException(status_code=400, detail={"error": {"code": "INSUFFICIENT_STOCK", "message": str(e)}})


# ──────────────────────────────────────────────
# Order history
# ──────────────────────────────────────────────

@router.get("/", response_model=OrderListEnvelope)
def list_orders(user_info: dict = Depends(get_current_user_id)):
    user_id = user_info["user_id"]
    orders = get_user_orders(user_id)
    return OrderListEnvelope(
        data=[OrderListItemResponse(
            order_id=o.id,
            status=o.status,
            total_amount=o.total_amount,
            created_at=o.created_at,
        ) for o in orders],
        message=f"{len(orders)} order(s) found",
    )


@router.get("/{order_id}", response_model=OrderEnvelope)
def get_order(
    order_id: UUID,
    user_info: dict = Depends(get_current_user_id),
):
    user_id = user_info["user_id"]
    try:
        order = get_order_detail(user_id, str(order_id))
        return OrderEnvelope(
            data=OrderResponse(
                order_id=order.id,
                status=order.status,
                total_amount=order.total_amount,
                items=[OrderItemResponse.model_validate(item) for item in order.items.all()],
                shipping_address=ShippingAddressResponse(
                    name=order.shipping_name,
                    address_line1=order.shipping_address_line1,
                    address_line2=order.shipping_address_line2,
                    city=order.shipping_city,
                    state=order.shipping_state,
                    pincode=order.shipping_pincode,
                    phone=order.shipping_phone,
                ),
                created_at=order.created_at,
            ),
            message="Order found",
        )
    except OrderNotFoundError as e:
        raise HTTPException(status_code=404, detail={"error": {"code": "ORDER_NOT_FOUND", "message": str(e)}})
    except OrderAccessDeniedError as e:
        raise HTTPException(status_code=403, detail={"error": {"code": "ACCESS_DENIED", "message": str(e)}})