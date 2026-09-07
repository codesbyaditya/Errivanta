import time
import httpx

ORDER_SERVICE_URL = "http://127.0.0.1:8002"
PAYMENT_SERVICE_URL = "http://127.0.0.1:8003"


def log_response(name: str, response: httpx.Response):
    print(f"[{name}] -> Status: {response.status_code} | Body: {response.text[:80]}")


def run_traffic_tests():
    print("==================================================")
    print("🚀 Starting SDK Telemetry & Error Verification Test")
    print("==================================================")

    with httpx.Client(timeout=5.0) as client:
        # 1. Successful requests
        print("\n--- 1. Testing Normal Traffic (200 OK) ---")
        res = client.get(f"{ORDER_SERVICE_URL}/")
        log_response("Order Service Root", res)

        res = client.get(f"{ORDER_SERVICE_URL}/orders")
        log_response("Order Service List", res)

        res = client.post(
            f"{ORDER_SERVICE_URL}/orders/checkout?order_id=101&amount=250.0"
        )
        log_response("Order Checkout -> Payment Success", res)

        # 2. Client Errors (400 Bad Request, 402 Payment Required)
        print("\n--- 2. Testing Client Validation Errors (400 / 402) ---")
        res = client.post(
            f"{PAYMENT_SERVICE_URL}/payments/process",
            json={"order_id": 102, "amount": -50.0}
        )
        log_response("Payment Negative Amount (400)", res)

        res = client.post(
            f"{PAYMENT_SERVICE_URL}/payments/process",
            json={"order_id": 103, "amount": 50000.0}
        )
        log_response("Payment Exceeds Limit (402)", res)

        # 3. Unhandled Server Exceptions (500 Crashes)
        print("\n--- 3. Testing Unhandled Server Exceptions (500 Crashes) ---")
        try:
            res = client.get(f"{ORDER_SERVICE_URL}/orders/crash")
            log_response("Order Service Unhandled Crash", res)
        except Exception as e:
            print(f"[Order Service Crash] Captured client-side: {e}")

        try:
            res = client.get(f"{PAYMENT_SERVICE_URL}/payments/fail-database")
            log_response("Payment Database Failure", res)
        except Exception as e:
            print(f"[Payment DB Crash] Captured client-side: {e}")

        # 4. Downstream Error Propagation (Order calling Payment with crash order_id 999)
        print("\n--- 4. Testing Cascading Inter-Service Errors ---")
        res = client.post(
            f"{ORDER_SERVICE_URL}/orders/checkout?order_id=999&amount=500.0"
        )
        log_response("Cascading Checkout Failure (502)", res)

    print("\n==================================================")
    print("✅ Traffic generation finished!")
    print("Check your Errivanta Dashboard / Monitoring API to see if telemetry and errors appear.")
    print("==================================================")


if __name__ == "__main__":
    run_traffic_tests()
