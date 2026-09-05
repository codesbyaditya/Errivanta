# ServiceWatch Python SDK (`servicewatch-sdk`)

A lightweight, non-blocking telemetry and error monitoring SDK for FastAPI applications.

---

## 📦 Installation

```bash
pip install ./servicewatch-sdk
```

---

## 🚀 Quickstart

```python
from fastapi import FastAPI
from servicewatch import ServiceWatch

app = FastAPI(title="My Service")

# Initialize ServiceWatch
monitor = ServiceWatch(
    service_name="payment-service",
    api_key="sw_live_xxxxxxxx",
    monitoring_url="http://localhost:8001"
)

# Attach monitoring middleware
monitor.init_app(app)

@app.get("/items")
def get_items():
    return [{"id": 1, "name": "item"}]
```

---

## 🛡️ Reliability Guarantees

* **Zero Application Interruption**: If the ServiceWatch Monitoring API is slow or down, the SDK swallows errors and allows your application traffic to proceed without interruption.
* **Automatic Latency Tracking**: Accurately measures end-to-end endpoint execution time in milliseconds.
* **Automatic Exception Capture**: Catches and reports unhandled application crashes and 500 errors.
