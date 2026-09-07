# Errivanta SDK Verification Demo Apps

This directory contains 2 independent FastAPI microservices configured with the **Errivanta SDK** to verify that telemetry, metrics, and errors are captured accurately.

## Architecture

```
[traffic_generator.py]
      │
      ├──► [Order Service (Port 8002)] (Errivanta SDK attached)
      │          │
      │          ▼
      └──► [Payment Service (Port 8003)] (Errivanta SDK attached)
                 │
                 ▼
         [Errivanta Monitoring API (Port 8001)]
```

---

## Quick Start Guide

### 1. Install SDK locally (editable mode)
Make sure the SDK is installed in your Python environment:
```bash
pip install -e ../errivanta-sdk
pip install fastapi uvicorn httpx pydantic
```

### 2. Start Errivanta Monitoring API Backend
Ensure your monitoring backend is running on `http://localhost:8001` (or set `MONITORING_URL`).

### 3. Start Both Services

**Terminal 1 (Order Service):**
```bash
python order_service.py
```
*Runs on `http://127.0.0.1:8002`*

**Terminal 2 (Payment Service):**
```bash
python payment_service.py
```
*Runs on `http://127.0.0.1:8003`*

---

### 4. Send Test Traffic & Error Payloads

**Terminal 3 (Traffic Simulator):**
```bash
python traffic_generator.py
```

This will trigger:
- `200 OK` normal successful routes
- `400 Bad Request` validation error
- `402 Payment Required` business logic error
- `500 Unhandled Exception` (Order service crash & Payment DB connection simulation)
- `502 Bad Gateway` downstream cascading service error

---

### 5. Verify in Dashboard / Monitoring API
- Open your dashboard / API endpoints to confirm:
  1. Requests per minute (RPM) and latency percentiles are tracked for both services.
  2. Errors from both services show up under **Incidents / Error Traces**.
  3. Service names `order-service` and `payment-service` are segregated properly.
