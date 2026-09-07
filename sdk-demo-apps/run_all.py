import subprocess
import sys
import time
import os
import signal

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def cleanup_ports():
    """Kill any existing processes running on ports 8002 and 8003 on Windows."""
    if sys.platform == "win32":
        for port in [8002, 8003]:
            try:
                cmd = f"Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess | ForEach-Object {{ Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }}"
                subprocess.run(["powershell", "-Command", cmd], capture_output=True)
            except Exception:
                pass

def main():
    print("[INIT] Cleaning up ports 8002 and 8003...")
    cleanup_ports()
    time.sleep(1)

    print("[START] Launching Order Service (Port 8002) and Payment Service (Port 8003)...")
    
    order_proc = subprocess.Popen([sys.executable, "order_service.py"])
    payment_proc = subprocess.Popen([sys.executable, "payment_service.py"])
    
    print("\n[READY] Microservices started successfully!")
    print("- Order Service:   http://127.0.0.1:8002")
    print("- Payment Service: http://127.0.0.1:8003")
    print("\nTelemetry reporting destination: https://errivanta.onrender.com\n")
    print("Press Ctrl+C to terminate both services.\n")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping services...")
        order_proc.terminate()
        payment_proc.terminate()
        cleanup_ports()
        print("Done.")

if __name__ == "__main__":
    main()
