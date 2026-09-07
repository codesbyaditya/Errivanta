import subprocess
import sys
import time

def main():
    print("🚀 Launching Order Service (Port 8002) and Payment Service (Port 8003)...")
    
    order_proc = subprocess.Popen([sys.executable, "order_service.py"])
    payment_proc = subprocess.Popen([sys.executable, "payment_service.py"])
    
    print("\n✅ Services started!")
    print("- Order Service: http://127.0.0.1:8002")
    print("- Payment Service: http://127.0.0.1:8003")
    print("\nPress Ctrl+C to terminate both services.\n")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping services...")
        order_proc.terminate()
        payment_proc.terminate()
        print("Done.")

if __name__ == "__main__":
    main()
