"""
Order service entry point. Runs on port 8003.
Auth=8001, Product=8002, Order=8003.

Important: Order service shares SECRET_KEY with Auth service.
Both must have the same SECRET_KEY in their .env files.
"""

import os
import django
from dotenv import load_dotenv

# Start Redis event consumer in background thread
from apps.orders.event_consumer import start_event_consumer
start_event_consumer()

load_dotenv()
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apps.orders.routes import router as orders_router

app = FastAPI(
    title="Order Service",
    description="Manages cart, checkout, and order history.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000",
                   "http://192.168.0.126:3000",],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(orders_router)

@app.get("/health", tags=["System"])
def health_check():
    return {"status": "ok", "service": "orders"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8003, reload=True)