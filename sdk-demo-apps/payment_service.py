import os
import random
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from errivanta import Errivanta

# Load environment variables (.env in current directory or parent)
load_dotenv()

# 1. Initialize FastAPI app
app = FastAPI(title="Payment Service", version="1.0.0")

# 2. Configure and attach Errivanta SDK
monitor = Errivanta(
    service_name="payment-service",
    api_key="sw_ab1c26f47058eb7d66e92459e638d526",
    monitoring_url="https://errivanta.onrender.com"
)
monitor.init_app(app)


class PaymentRequest(BaseModel):
    order_id: int
    amount: float


@app.get("/")
async def root():
    return {"service": "payment-service", "status": "running"}


@app.post("/payments/process")
async def process_payment(payment: PaymentRequest):
    # Test error cases to see how SDK captures different status codes:
    if payment.amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="Invalid payment amount. Amount must be greater than zero."
        )

    if payment.amount > 10000:
        # Simulate gateway rejection / card limit
        raise HTTPException(
            status_code=402,
            detail="Payment Required: Card limit exceeded for high-value transaction."
        )

    # Simulate random occasional payment gateway failure (500)
    if payment.order_id == 999:
        raise RuntimeError("Payment Gateway Timeout / Internal Gateway Failure!")

    return {
        "status": "SUCCESS",
        "transaction_id": f"txn_{random.randint(10000, 99999)}",
        "order_id": payment.order_id,
        "amount": payment.amount
    }


@app.get("/payments/fail-database")
async def simulated_database_failure():
    # Demonstrates database connection crash error capture in SDK
    raise ConnectionRefusedError("Unable to connect to Payment Database pool on port 5432!")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("payment_service:app", host="127.0.0.1", port=8003, reload=True)
