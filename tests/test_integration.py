import os
import sys
import time
import socket
import subprocess
import pytest
import httpx


def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


def wait_for_server(port: int, timeout: float = 10.0):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return True
        except (OSError, ConnectionRefusedError):
            time.sleep(0.2)
    return False


@pytest.fixture(scope="module")
def servers():
    mon_port = get_free_port()
    pay_port = get_free_port()
    ord_port = get_free_port()

    from pathlib import Path
    root = Path(__file__).parent.parent
    mon_dir = str(root / "monitoring-api")
    pay_dir = str(root / "payment-service")
    ord_dir = str(root / "order-service")
    python_exe = sys.executable

    # Setup environment variables
    env_mon = os.environ.copy()
    env_mon["DATABASE_URL"] = "sqlite:///./test_monitoring_p2.db"
    env_mon["PORT"] = str(mon_port)

    env_pay = os.environ.copy()
    env_pay["DATABASE_URL"] = "sqlite:///./test_payment_p2.db"
    env_pay["PORT"] = str(pay_port)
    env_pay["SERVICEWATCH_URL"] = f"http://127.0.0.1:{mon_port}"
    env_pay["SERVICEWATCH_API_KEY"] = "sw_demo_payment_key_12345"

    env_ord = os.environ.copy()
    env_ord["DATABASE_URL"] = "sqlite:///./test_order_p2.db"
    env_ord["PORT"] = str(ord_port)
    env_ord["SERVICEWATCH_URL"] = f"http://127.0.0.1:{mon_port}"
    env_ord["SERVICEWATCH_API_KEY"] = "sw_demo_order_key_12345"

    mon_proc = subprocess.Popen(
        [python_exe, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(mon_port), "--app-dir", mon_dir],
        env=env_mon,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    pay_proc = subprocess.Popen(
        [python_exe, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(pay_port), "--app-dir", pay_dir],
        env=env_pay,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    ord_proc = subprocess.Popen(
        [python_exe, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(ord_port), "--app-dir", ord_dir],
        env=env_ord,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    assert wait_for_server(mon_port), f"Monitoring server on port {mon_port} did not start"
    assert wait_for_server(pay_port), f"Payment server on port {pay_port} did not start"
    assert wait_for_server(ord_port), f"Order server on port {ord_port} did not start"

    yield {
        "monitoring_url": f"http://127.0.0.1:{mon_port}",
        "payment_url": f"http://127.0.0.1:{pay_port}",
        "order_url": f"http://127.0.0.1:{ord_port}",
    }

    mon_proc.terminate()
    pay_proc.terminate()
    ord_proc.terminate()
    mon_proc.wait(timeout=3)
    pay_proc.wait(timeout=3)
    ord_proc.wait(timeout=3)

    for f in ["test_monitoring_p2.db", "test_payment_p2.db", "test_order_p2.db"]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Test 1: Multi-Service Health & Registration
# ---------------------------------------------------------------------------
def test_all_services_healthy(servers):
    mon_url = servers["monitoring_url"]
    pay_url = servers["payment_url"]
    ord_url = servers["order_url"]

    # All three services return healthy
    assert httpx.get(f"{mon_url}/health").status_code == 200
    assert httpx.get(f"{pay_url}/health").status_code == 200
    assert httpx.get(f"{ord_url}/health").status_code == 200

    # Dashboard overview recognizes all registered services
    overview = httpx.get(f"{mon_url}/api/v1/dashboard/overview").json()
    assert overview["total_services"] >= 2
    assert overview["healthy_services"] >= 2


# ---------------------------------------------------------------------------
# Test 2: Multi-Service Business Traffic Flow & Dashboard Aggregation
# ---------------------------------------------------------------------------
def test_multi_service_traffic_and_metrics(servers):
    mon_url = servers["monitoring_url"]
    pay_url = servers["payment_url"]
    ord_url = servers["order_url"]

    # 1. Create a payment in Payment Service
    pay_res = httpx.post(f"{pay_url}/payments", json={"user_id": 1, "amount": 500.0, "currency": "INR"})
    assert pay_res.status_code == 201

    # 2. Create an order in Order Service
    ord_res = httpx.post(f"{ord_url}/orders", json={"customer_name": "Test Customer", "item_count": 2, "total_amount": 120.0})
    assert ord_res.status_code == 201

    time.sleep(0.5)

    # 3. Verify Dashboard services list contains updated metrics for both
    services = httpx.get(f"{mon_url}/api/v1/services").json()
    service_names = [s["name"] for s in services]
    assert "payment-service" in service_names
    assert "order-service" in service_names

    pay_svc = next(s for s in services if s["name"] == "payment-service")
    ord_svc = next(s for s in services if s["name"] == "order-service")

    assert pay_svc["total_requests_last_5m"] >= 1
    assert ord_svc["total_requests_last_5m"] >= 1
    assert pay_svc["health"] == "HEALTHY"
    assert ord_svc["health"] == "HEALTHY"


# ---------------------------------------------------------------------------
# Test 3: Real Database Failure Simulation & Automatic Incident Creation
# ---------------------------------------------------------------------------
def test_real_failure_incident_creation_and_deduplication(servers):
    mon_url = servers["monitoring_url"]
    pay_url = servers["payment_url"]

    # Trigger threshold-crossing failures on Payment Service (e.g. 500 errors)
    for _ in range(8):
        # We can trigger 422 or direct error simulation
        httpx.post(f"{pay_url}/payments", json={"user_id": 1, "amount": -10.0, "currency": "INR"})

    time.sleep(0.5)

    # Verify metrics show error rate > 10% and health changed to CRITICAL
    services = httpx.get(f"{mon_url}/api/v1/services").json()
    pay_svc = next(s for s in services if s["name"] == "payment-service")
    assert pay_svc["error_rate"] >= 10.0
    assert pay_svc["health"] == "CRITICAL"

    # Verify an Incident was automatically opened
    incidents = httpx.get(f"{mon_url}/api/v1/incidents?status=OPEN").json()
    assert len(incidents) >= 1
    open_inc = next(i for i in incidents if i["service_name"] == "payment-service")
    assert open_inc["severity"] == "CRITICAL"
    assert open_inc["status"] == "OPEN"

    incident_id = open_inc["id"]

    # Send more errors -> test deduplication (incident count should not increase)
    for _ in range(4):
        httpx.post(f"{pay_url}/payments", json={"user_id": 1, "amount": -10.0, "currency": "INR"})

    time.sleep(0.5)

    incidents_after = httpx.get(f"{mon_url}/api/v1/incidents?status=OPEN").json()
    open_incs_for_pay = [i for i in incidents_after if i["service_name"] == "payment-service"]
    assert len(open_incs_for_pay) == 1
    assert open_incs_for_pay[0]["id"] == incident_id

    # 4. Resolve the incident via Dashboard API
    resolve_res = httpx.patch(f"{mon_url}/api/v1/incidents/{incident_id}/resolve")
    assert resolve_res.status_code == 200
    assert resolve_res.json()["incident"]["status"] == "RESOLVED"

    # Verify it is no longer in OPEN list
    open_incs_final = httpx.get(f"{mon_url}/api/v1/incidents?status=OPEN").json()
    assert not any(i["id"] == incident_id for i in open_incs_final)
