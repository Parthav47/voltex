"""
Payment service routes.

Three endpoints:
  POST /api/payments/initiate              — internal, called by Order service
  POST /api/payments/webhook/razorpay      — called by Razorpay servers
  GET  /api/payments/{order_id}            — check payment status
  POST /api/payments/test/confirm/{order_id} — TEST ONLY, simulates webhook
"""

import os
from uuid import UUID
from fastapi import APIRouter, HTTPException, Header, Request, status
from dotenv import load_dotenv

from .models import Payment
from .schemas import (
    InitiatePaymentRequest,
    InitiatePaymentResponse,
    PaymentStatusEnvelope,
    PaymentStatusResponse,
    MessageResponse,
)
from .service import (
    initiate_payment,
    handle_webhook,
    get_payment_by_order,
    PaymentNotFoundError,
    InvalidWebhookError,
    PaymentInitiationError,
    _publish_event,
)

load_dotenv()

router = APIRouter(prefix="/api/payments", tags=["Payments"])
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "")


def verify_internal_key(x_internal_key: str = Header(None)):
    """Shared internal key guard for service-to-service calls."""
    if not x_internal_key or x_internal_key != INTERNAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Invalid internal key"}},
        )


@router.post("/initiate", response_model=InitiatePaymentResponse, status_code=201)
def initiate(
    body: InitiatePaymentRequest,
    x_internal_key: str = Header(None),
):
    """
    Create a Razorpay order.
    Called by Order service during checkout.
    Returns razorpay_order_id for frontend payment popup.
    """
    verify_internal_key(x_internal_key)

    try:
        result = initiate_payment(str(body.order_id), float(body.amount))
        return InitiatePaymentResponse(
            data=result,
            message="Payment initiated",
        )
    except PaymentInitiationError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": {"code": "PAYMENT_INIT_FAILED", "message": str(e)}},
        )


@router.post("/webhook/razorpay")
async def razorpay_webhook(request: Request):
    """
    Receive payment result from Razorpay.

    CRITICAL: reads raw bytes — NOT parsed JSON.
    Must always return 200 — Razorpay retries on any other status.
    """
    raw_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")

    try:
        handle_webhook(raw_body, signature)
    except InvalidWebhookError:
        return {"status": "ignored"}
    except Exception as e:
        print(f"Webhook processing error: {e}")
        return {"status": "error logged"}

    return {"status": "ok"}


@router.get("/{order_id}", response_model=PaymentStatusEnvelope)
def get_payment_status(order_id: UUID):
    """
    Get payment status for an order.
    Called by frontend on the confirmation page.
    """
    try:
        payment = get_payment_by_order(str(order_id))
        return PaymentStatusEnvelope(
            data=PaymentStatusResponse.model_validate(payment),
            message="Payment found",
        )
    except PaymentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "PAYMENT_NOT_FOUND", "message": str(e)}},
        )


@router.post("/test/confirm/{order_id}")
def test_confirm_payment(
    order_id: str,
    x_internal_key: str = Header(None),
):
    """
    TEST ONLY — simulates a successful Razorpay webhook.
    Marks payment as success and publishes payment_success event to Redis.
    Remove this endpoint before going to production.
    """
    verify_internal_key(x_internal_key)

    try:
        payment = Payment.objects.get(order_id=order_id)
    except Payment.DoesNotExist:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "Payment not found"}}
        )

    # Simulate what a real Razorpay webhook would do
    payment.status = Payment.STATUS_SUCCESS
    payment.gateway_payment_id = f"test_pay_{order_id[:8]}"
    payment.payment_method = "test"
    payment.save(update_fields=[
        "status", "gateway_payment_id", "payment_method", "updated_at"
    ])

    # Publish same event structure as real webhook
    _publish_event("payment_success", {
        "order_id": str(payment.order_id),
        "payment_id": str(payment.id),
        "amount": payment.amount,
    })

    return {"message": f"Payment confirmed for order {order_id}"}

@router.post("/test/confirm/{order_id}")
def test_confirm_payment(
    order_id: str,
    user_email: str = "test@example.com",
    user_name: str = "Customer",
    x_internal_key: str = Header(None),
):
    verify_internal_key(x_internal_key)

    try:
        payment = Payment.objects.get(order_id=order_id)
    except Payment.DoesNotExist:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Payment not found"}})

    payment.status = Payment.STATUS_SUCCESS
    payment.gateway_payment_id = f"test_pay_{order_id[:8]}"
    payment.payment_method = "test"
    payment.save(update_fields=["status", "gateway_payment_id", "payment_method", "updated_at"])

    _publish_event("payment_success", {
        "order_id": str(payment.order_id),
        "payment_id": str(payment.id),
        "amount": payment.amount,
        "user_email": user_email,
        "user_name": user_name,
    })

    return {"message": f"Payment confirmed for order {order_id}"}