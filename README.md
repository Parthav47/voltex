# Voltex — Single Product E-Commerce Platform

A production-grade microservices e-commerce platform built for learning distributed systems architecture. Sells a single hero product (ProBuds X1 wireless earbuds) with a complete purchase flow — browse, cart, checkout, payment, and email confirmation.



---

## Architecture Overview
```
┌───────────────────────────────────────────────────────────────┐
│                       Next.js Frontend                        │
│                  (TypeScript + Tailwind CSS)                  │
└───────────────────────────────┬───────────────────────────────┘
                                │ HTTP
                                ▼
                    ┌─────────────────────┐
                    │    Each Service     │
                    │   on its own port   │
                    └──────────┬──────────┘
                               │
        ┌───────────────┬──────┼──────┬───────────────┐
        │               │      │      │               │
        ▼               ▼      ▼      ▼               ▼
   ┌─────────┐     ┌─────────┐ ┌─────────┐     ┌─────────┐
   │  Auth   │     │ Product │ │  Order  │     │ Payment │
   │  :8001  │     │  :8002  │ │  :8003  │     │  :8004  │
   └────┬────┘     └────┬────┘ └────┬────┘     └────┬────┘
        │               │           │               │
        ▼               ▼           ▼               ▼
   ┌─────────┐     ┌─────────┐ ┌─────────┐     ┌─────────┐
   │ auth db │     │ prod db │ │order db │     │paymentdb│
   └─────────┘     └─────────┘ └─────────┘     └─────────┘

                                   │
                                   │ payment_success event
                                   ▼
                        ┌──────────────────────┐
                        │      Redis Pub/Sub   │
                        └──────────┬───────────┘
                                   │
                                   ▼
                        ┌──────────────────────┐
                        │ Notification Service │
                        │    (Email Sender)    │
                        └──────────────────────┘
```

**5 microservices, each with its own PostgreSQL database. Services communicate via REST APIs (sync) and Redis pub/sub (async).**

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16, TypeScript, Tailwind CSS, App Router |
| Backend | Python FastAPI, Django ORM |
| Database | PostgreSQL (one per service) |
| Message broker | Redis pub/sub |
| Auth | JWT (access + refresh tokens), bcrypt |
| Payment | Razorpay |
| Email | SMTP (Gmail) |

---

## Services

| Service | Port | Responsibility |
|---|---|---|
| Auth | 8001 | Registration, login, JWT, refresh tokens |
| Product | 8002 | Product catalog, stock management |
| Order | 8003 | Cart, checkout, order lifecycle |
| Payment | 8004 | Razorpay integration, webhook handling |
| Notification | — | Email delivery via Redis events |
| Frontend | 3000 | Next.js web app |

---

## Prerequisites

- Python 3.11+
- Node.js 20+ (LTS)
- PostgreSQL 18
- Docker Desktop (for Redis)
- Git

---

## Project Structure

```
ZIPDROP/
├── auth_service/
├── product_service/
├── order_service/
├── payment_service/
├── notification_service/
└── frontend/
```

---

## Setup & Installation

### 1 — Clone the repository

```bash
git clone https://github.com/yourusername/voltex.git
cd voltex
```

### 2 — Start Redis via Docker

```bash
docker run -d --name voltex-redis -p 6379:6379 redis:alpine
docker exec -it voltex-redis redis-cli ping
# Expected: PONG
```
### 2.5 — Add PostgreSQL to PATH (Windows)

Run this in PowerShell to use `psql` in the current session:

```powershell
$env:PATH += ";C:\Program Files\PostgreSQL\18\bin"
```

### 3 — Create PostgreSQL databases

```sql
CREATE DATABASE auth_db;
CREATE DATABASE product_db;
CREATE DATABASE order_db;
CREATE DATABASE payment_db;
CREATE DATABASE notification_db;
```

### 4 — Set up each Python service

Repeat these steps for each service (`auth_service`, `product_service`, `order_service`, `payment_service`, `notification_service`):

```bash
cd <service_name>

# Create and activate virtual environment
python -m venv venv
venv\Scripts\Activate     # Windows
source venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Copy and fill in environment variables
copy .env.example .env
# Edit .env with your values

# Run migrations
mkdir apps\<app_name>\migrations
type nul > apps\<app_name>\migrations\__init__.py
python manage.py makemigrations <app_name>
python manage.py migrate

cd ..
```

### 5 — Environment variables

Each service has a `.env.example`. Key variables:

**Auth service** (`auth_service/.env`):
```env
SECRET_KEY=your-32-char-secret-key
ACCESS_TOKEN_EXPIRE_SECONDS=900
REFRESH_TOKEN_EXPIRE_SECONDS=604800
DATABASE_URL=postgresql://postgres:password@localhost:5432/auth_db
DJANGO_DEBUG=True
```

**Product service** (`product_service/.env`):
```env
INTERNAL_API_KEY=your-internal-api-key
DATABASE_URL=postgresql://postgres:password@localhost:5432/product_db
DJANGO_DEBUG=True
```

**Order service** (`order_service/.env`):
```env
SECRET_KEY=same-key-as-auth-service
INTERNAL_API_KEY=same-internal-api-key
PRODUCT_SERVICE_URL=http://localhost:8002
PAYMENT_SERVICE_URL=http://localhost:8004
REDIS_URL=redis://localhost:6379
DATABASE_URL=postgresql://postgres:password@localhost:5432/order_db
DJANGO_DEBUG=True
```

**Payment service** (`payment_service/.env`):
```env
RAZORPAY_KEY_ID=rzp_test_your_key
RAZORPAY_KEY_SECRET=your_secret
RAZORPAY_WEBHOOK_SECRET=your_webhook_secret
INTERNAL_API_KEY=same-internal-api-key
REDIS_URL=redis://localhost:6379
DATABASE_URL=postgresql://postgres:password@localhost:5432/payment_db
DJANGO_DEBUG=True
```

**Notification service** (`notification_service/.env`):
```env
REDIS_URL=redis://localhost:6379
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_EMAIL=your-gmail@gmail.com
SMTP_PASSWORD=your-16-char-app-password
EMAIL_FROM_NAME=Voltex
DATABASE_URL=postgresql://postgres:password@localhost:5432/notification_db
DJANGO_DEBUG=True
```

> **Important:** `SECRET_KEY` must be identical in `auth_service` and `order_service` — Order service verifies JWTs using this shared key without calling Auth service.

> **Important:** `INTERNAL_API_KEY` must be identical across all services that use it.

### 6 — Seed the product

```bash
cd product_service
venv\Scripts\Activate

python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from apps.products.models import Product
Product.objects.create(
    name='ProBuds X1',
    sku='PBUD-X1-BLK',
    description='Premium wireless earbuds with ANC and 40hr battery.',
    price='2999.00',
    stock_count=48,
    is_active=True,
    images=['https://placehold.co/400x400?text=ProBuds+X1'],
    weight_grams=45,
    dimensions='6x4x3cm',
    meta_title='ProBuds X1 Wireless Earbuds',
    meta_description='Buy ProBuds X1 — premium ANC earbuds.',
)
print('Product seeded.')
"
```

### 7 — Set up the frontend

```bash
cd frontend
npm install
cp .env.example .env.local  # if applicable
```

---

## Running the Application

Open **6 separate terminals** and run each command:

```bash
# Terminal 1 — Auth service
cd auth_service && venv\Scripts\Activate && uvicorn main:app --reload --port 8001

# Terminal 2 — Product service
cd product_service && venv\Scripts\Activate && uvicorn main:app --reload --port 8002

# Terminal 3 — Order service
cd order_service && venv\Scripts\Activate && uvicorn main:app --reload --port 8003

# Terminal 4 — Payment service
cd payment_service && venv\Scripts\Activate && uvicorn main:app --reload --port 8004

# Terminal 5 — Notification service
cd notification_service && venv\Scripts\Activate && python main.py

# Terminal 6 — Frontend
cd frontend && npm run dev
```

Visit `http://localhost:3000`

---

## API Documentation

Each FastAPI service auto-generates interactive docs:

| Service | Swagger UI |
|---|---|
| Auth | http://localhost:8001/docs |
| Product | http://localhost:8002/docs |
| Order | http://localhost:8003/docs |
| Payment | http://localhost:8004/docs |

---

## Key API Endpoints

### Auth service
```
POST /api/auth/register     — create account
POST /api/auth/login        — get access + refresh tokens
POST /api/auth/refresh      — refresh access token
POST /api/auth/logout       — revoke refresh token
GET  /api/auth/me           — get current user
```

### Product service
```
GET   /api/products/              — list all active products
GET   /api/products/{id}          — get product detail
PATCH /api/products/{id}/stock    — update stock (internal)
```

### Order service
```
GET    /api/orders/cart                  — get cart
POST   /api/orders/cart/items            — add to cart
PATCH  /api/orders/cart/items/{id}       — update quantity
DELETE /api/orders/cart/items/{id}       — remove item
POST   /api/orders/checkout              — create order
GET    /api/orders/                      — order history
GET    /api/orders/{id}                  — order detail
```

### Payment service
```
POST /api/payments/initiate                  — create Razorpay order (internal)
POST /api/payments/webhook/razorpay          — Razorpay webhook
GET  /api/payments/{order_id}                — payment status
POST /api/payments/test/confirm/{order_id}   — simulate payment (test only)
```

---

## Testing the Payment Flow

Since Razorpay requires KYC for live payments, use the test confirmation endpoint:

1. Add product to cart and checkout via frontend
2. Copy the `order_id` from the URL
3. Initiate payment via `POST /api/payments/initiate`
4. Simulate payment success:

```bash
curl -X POST "http://localhost:8004/api/payments/test/confirm/{order_id}?user_email=your@email.com&user_name=YourName" \
  -H "X-Internal-Key: your-internal-api-key"
```

5. Order status updates to `paid` automatically
6. Confirmation email arrives in your inbox

---

## Security Highlights

- Passwords hashed with bcrypt (rounds=12)
- Access tokens expire in 15 minutes (in-memory only)
- Refresh tokens stored in httpOnly cookies (JS inaccessible)
- Refresh token rotation on every use
- Internal service calls protected by shared API key
- Razorpay webhooks verified with HMAC-SHA256 signature
- `SELECT FOR UPDATE` prevents race conditions during concurrent checkouts
- Services never share databases — no cross-service DB joins

---

## Architecture Decisions

**Why database-per-service?**
Each service can fail, scale, and deploy independently. A crash in the Notification service doesn't affect checkout.

**Why JWT for auth across services?**
Order service verifies tokens locally using the shared `SECRET_KEY` without calling Auth service on every request — no inter-service latency on protected routes.

**Why Redis pub/sub for notifications?**
Payment service doesn't need to know Notification service exists. It publishes an event and moves on. This decoupling means you can add new consumers (SMS, push notifications) without changing any existing code.

**Why separate access and refresh tokens?**
Access tokens expire in 15 minutes, limiting damage from theft. Refresh tokens live in httpOnly cookies — inaccessible to JavaScript, immune to XSS attacks.

---

## Pages

| Route | Description | Auth required |
|---|---|---|
| `/` | Landing page with hero product | No |
| `/product/:id` | Product detail + add to cart | No (cart needs auth) |
| `/login` | Login / Register tabs | No |
| `/cart` | Cart with quantity controls | Yes |
| `/checkout` | Shipping address + payment | Yes |
| `/orders` | Order history | Yes |
| `/orders/:id` | Order detail / confirmation | Yes |

---

## Roadmap — Future Enhancements

- **Razorpay Webhook Integration**: Move from test confirmation endpoint to full live Razorpay webhook handling with proper signature verification and idempotency
- **Service Runner Script**: Create a single command (batch/shell script) to spawn all 6 services simultaneously instead of manual terminal management
- **UI Refinements**: Improve checkout flow, add order tracking status visualization, and enhance mobile responsiveness
- **Seed Dummy Data**: Expand product catalog with multiple SKUs, and generate realistic order/user history for testing and demo purposes

---

## Health Checks

```bash
curl http://localhost:8001/health  # {"status":"ok","service":"auth"}
curl http://localhost:8002/health  # {"status":"ok","service":"products"}
curl http://localhost:8003/health  # {"status":"ok","service":"orders"}
curl http://localhost:8004/health  # {"status":"ok","service":"payments"}
```

---

## Known Limitations

- Razorpay integration requires KYC for live payments — test mode works fully
- No admin panel for product/order management (use Django shell or API directly)
- Notification service uses fire-and-forget — no retry on email failure
- No HTTPS in development (required for production deployment)

---

## Development & Learning

- **Built with Claude**: This project was developed with Claude for error handling, debugging complex microservice interactions, and comprehensive code documentation across all services.

- **Learning by Building**: Intentionally designed and tested error scenarios to understand proper exception handling, distributed system failures, and recovery mechanisms across a real-world e-commerce architecture and tech stack.

---

## License

MIT
