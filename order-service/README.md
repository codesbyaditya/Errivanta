# Order Service (`order-service`)

A real microservice managing orders, integrated with the **ServiceWatch** telemetry monitoring SDK.

---

## 🚀 Endpoints

* `GET /health`: Health status.
* `POST /orders`: Place a new order (`customer_name`, `item_count`, `total_amount`).
* `GET /orders/{order_id}`: Look up order details.

---

## 🏃 How to Run

```powershell
cd order-service
..\payment-service\venv\Scripts\Activate.ps1
uvicorn app.main:app --port 8002 --reload
```
Interactive Documentation: [http://localhost:8002/docs](http://localhost:8002/docs)
