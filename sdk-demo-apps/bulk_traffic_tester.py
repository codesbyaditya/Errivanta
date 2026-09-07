import time
import random
import sys
import httpx
from concurrent.futures import ThreadPoolExecutor

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ORDER_SERVICE_URL = "http://127.0.0.1:8002"
PAYMENT_SERVICE_URL = "http://127.0.0.1:8003"

TOTAL_REQUESTS = 100
CONCURRENCY = 10


def send_single_request(i: int):
    with httpx.Client(timeout=5.0) as client:
        # Mix of normal requests and error requests to exceed the 10% critical error threshold
        roll = random.random()
        try:
            if roll < 0.40:
                # Normal 200 OK
                res = client.get(f"{ORDER_SERVICE_URL}/orders")
                return f"[{i}] Order List -> {res.status_code}"
            elif roll < 0.65:
                # Normal Checkout (200 OK)
                res = client.post(f"{ORDER_SERVICE_URL}/orders/checkout?order_id={i}&amount=150.0")
                return f"[{i}] Checkout Success -> {res.status_code}"
            elif roll < 0.80:
                # Validation error 400
                res = client.post(
                    f"{PAYMENT_SERVICE_URL}/payments/process",
                    json={"order_id": i, "amount": -10.0}
                )
                return f"[{i}] Payment Bad Request -> {res.status_code}"
            elif roll < 0.90:
                # Database crash 500
                try:
                    res = client.get(f"{PAYMENT_SERVICE_URL}/payments/fail-database")
                    return f"[{i}] Payment DB Crash -> {res.status_code}"
                except Exception as e:
                    return f"[{i}] Payment DB Crash (Client caught): {e}"
            else:
                # Order service crash 500
                try:
                    res = client.get(f"{ORDER_SERVICE_URL}/orders/crash")
                    return f"[{i}] Order Crash -> {res.status_code}"
                except Exception as e:
                    return f"[{i}] Order Crash (Client caught): {e}"
        except Exception as exc:
            return f"[{i}] Request failed: {exc}"


def run_bulk_traffic(total: int = TOTAL_REQUESTS, concurrency: int = CONCURRENCY):
    print("=" * 60)
    print("🚀 STARTING BULK TRAFFIC INJECTION")
    print(f"Total Requests: {total} | Concurrency: {concurrency}")
    print("Intentional Error Ratio: ~35% (Exceeds 10% Critical Alert Threshold)")
    print("=" * 60)

    start_time = time.time()
    results = []

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(send_single_request, i) for i in range(1, total + 1)]
        for f in futures:
            res = f.result()
            results.append(res)
            print(res)

    duration = time.time() - start_time
    print("\n" + "=" * 60)
    print(f"✅ Finished {total} requests in {duration:.2f}s ({total/duration:.1f} req/s)")
    print("=" * 60)
    print("🚨 High error rates will now evaluate in the Errivanta incident engine.")
    print("📧 Check your designated email inbox for the critical incident alert.")
    print("=" * 60)


if __name__ == "__main__":
    run_bulk_traffic(total=80, concurrency=8)
