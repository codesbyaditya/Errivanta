import os
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from errivanta import Errivanta

# Load environment variables (.env in current directory or parent)
load_dotenv()

# 1. Initialize FastAPI app

# 2. Configure and attach Errivanta SDK


app = FastAPI(title="Order Service")
PAYMENT_SERVICE_URL = os.getenv("PAYMENT_SERVICE_URL", "http://localhost:8003")

# 1. Initialize Errivanta Monitoring
monitor = Errivanta(
    service_name="order-service",
    api_key="sw_f2ed432dead6692e4ea0b1a8795483ee",
    monitoring_url="https://errivanta.onrender.com/api/v1/telemetry"
)
monitor.init_app(app)

@app.get("/")
async def root():
    return {"service": "order-service", "status": "running"}


@app.get("/orders")
async def list_orders():
    return [
        {"id": 101, "item": "Laptop", "price": 1200},
        {"id": 102, "item": "Wireless Mouse", "price": 25},
    ]


@app.post("/orders/checkout")
async def checkout_order(order_id: int, amount: float):
    # Simulates calling downstream Payment Service (Service 2)
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            response = await client.post(
                f"{PAYMENT_SERVICE_URL}/payments/process",
                json={"order_id": order_id, "amount": amount}
            )
            if response.status_code != 200:
                raise HTTPException(
                    status_code=502,
                    detail=f"Downstream payment service failed: {response.text}"
                )
            return {
                "message": "Order placed and paid successfully",
                "order_id": order_id,
                "payment": response.json()
            }
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Payment service unavailable: {str(exc)}"
            )


@app.get("/orders/crash")
async def simulated_crash():
    # Demonstrates unhandled exception capture by the SDK
    raise RuntimeError("Critical unexpected bug in Order Service!")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("order_service:app", host="127.0.0.1", port=8002, reload=True)
