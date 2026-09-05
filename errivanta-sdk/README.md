# Errivanta Python SDK (`errivanta`)

Official Python SDK and non-blocking FastAPI middleware for the **Errivanta Observability & Monitoring Platform**.

---

## 📦 Installation

```bash
pip install errivanta
```

---

## ⚡ Quickstart

Integrate Errivanta into any FastAPI or Starlette application in under 30 seconds:

```python
from fastapi import FastAPI
from errivanta import Errivanta

app = FastAPI(title="My Microservice")

# Initialize Errivanta monitoring
monitor = Errivanta(
    service_name="payment-service",
    api_key="your_organization_api_key",
    monitoring_url="https://your-errivanta-api.onrender.com"
)
monitor.init_app(app)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/payments/process")
def process_payment():
    return {"status": "success", "amount": 100}
```

---

## 🛡️ Non-Blocking & Fault Tolerant

- **Zero-Latency Overhead**: Telemetry events are dispatched in asynchronous fire-and-forget background tasks.
- **Fail-Safe**: If the monitoring server is unreachable or times out, exceptions are safely swallowed so your application never crashes or slows down.
- **Selective Route Filtering**: Automatically skips `/health`, `/docs`, and `/openapi.json` to keep metric logs clean.
