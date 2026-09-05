# ServiceWatch Monitoring API (`monitoring-api`)

The centralized telemetry ingestion API and storage engine for the ServiceWatch platform.

---

## 🚀 Features

* **Event Ingestion**: `POST /api/v1/events` receives latency, status, endpoint, error, and timestamp metrics.
* **API Key Authentication**: Authenticates every payload via `X-API-Key` to associate events with organizations and registered services.
* **PostgreSQL Storage**: Efficient relational schema with indices on `service_id`, `endpoint`, and `status_code`.

---

## 🏃 How to Run

```powershell
cd monitoring-api
..\payment-service\venv\Scripts\Activate.ps1
uvicorn app.main:app --port 8001 --reload
```

Interactive Docs: `http://localhost:8001/docs`
