import time
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


def send_error_request(index: int, error_type: str):
    with httpx.Client(timeout=10.0) as client:
        try:
            if error_type == "400_BAD_REQUEST":
                res = client.post(
                    f"{PAYMENT_SERVICE_URL}/payments/process",
                    json={"order_id": index, "amount": -25.0}
                )
                return f"[{index}] 400 Bad Request (Negative amount) -> HTTP {res.status_code}"

            elif error_type == "402_LIMIT_EXCEEDED":
                res = client.post(
                    f"{PAYMENT_SERVICE_URL}/payments/process",
                    json={"order_id": index, "amount": 99999.0}
                )
                return f"[{index}] 402 Payment Required (Card limit) -> HTTP {res.status_code}"

            elif error_type == "500_ORDER_CRASH":
                try:
                    res = client.get(f"{ORDER_SERVICE_URL}/orders/crash")
                    return f"[{index}] 500 Order Crash -> HTTP {res.status_code}"
                except Exception as e:
                    return f"[{index}] 500 Order Crash (Captured: {type(e).__name__})"

            elif error_type == "500_PAYMENT_DB_CRASH":
                try:
                    res = client.get(f"{PAYMENT_SERVICE_URL}/payments/fail-database")
                    return f"[{index}] 500 Payment DB Crash -> HTTP {res.status_code}"
                except Exception as e:
                    return f"[{index}] 500 Payment DB Crash (Captured: {type(e).__name__})"

            elif error_type == "502_CASCADING_FAILURE":
                res = client.post(f"{ORDER_SERVICE_URL}/orders/checkout?order_id=999&amount=500.0")
                return f"[{index}] 502 Cascading Downstream Failure -> HTTP {res.status_code}"

        except Exception as exc:
            return f"[{index}] Error request failed: {exc}"


def run_error_storm(rounds: int = 8):
    print("=" * 65)
    print("🚨 STARTING 100% ERROR STORM (Zero 200 OK Requests)")
    print("Simulating high-severity failures across microservices:")
    print("  - 400 Bad Request (Client Validation)")
    print("  - 402 Payment Required (Gateway Rule Rejection)")
    print("  - 500 Internal Server Error (Order Runtime Crash)")
    print("  - 500 Database Connection Crash (Payment DB Outage)")
    print("  - 502 Bad Gateway (Downstream Service Failure)")
    print("=" * 65)

    error_types = [
        "400_BAD_REQUEST",
        "402_LIMIT_EXCEEDED",
        "500_ORDER_CRASH",
        "500_PAYMENT_DB_CRASH",
        "502_CASCADING_FAILURE",
    ]

    total_requests = rounds * len(error_types)
    count = 0

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for r in range(rounds):
            for err in error_types:
                count += 1
                futures.append(executor.submit(send_error_request, count, err))

        for f in futures:
            result = f.result()
            print(result)

    print("\n" + "=" * 65)
    print(f"💥 Finished sending {total_requests} ERROR requests (100% Error Rate)!")
    print("📊 Check your Errivanta Dashboard for:")
    print("   1. 100% Error Rate Spike in Overview")
    print("   2. Red 'CRITICAL' Health Status Badge")
    print("   3. Open Incident created with full Stack Trace")
    print("📧 Check your designated Email Inbox for the Critical Incident Alert.")
    print("=" * 65)


if __name__ == "__main__":
    run_error_storm(rounds=6)
