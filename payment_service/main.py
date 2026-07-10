"""
Payment service entry point. Runs on port 8004.
Auth=8001, Product=8002, Order=8003, Payment=8004.
"""

import os
import django
from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apps.payments.routes import router as payments_router

app = FastAPI(
    title="Payment Service",
    description="Handles Razorpay integration and payment lifecycle.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(payments_router)

@app.get("/health", tags=["System"])
def health_check():
    return {"status": "ok", "service": "payments"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8004, reload=True)