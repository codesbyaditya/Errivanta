import os
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

from pathlib import Path

# Load root .env
root_env = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=root_env, override=True)

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "errivanta@gmail.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM_EMAIL", "errivanta@gmail.com")
# Recipient can be passed via command-line (e.g. python test_email_delivery.py myuser@example.com)
if len(sys.argv) > 1 and "@" in sys.argv[1]:
    RECIPIENT = sys.argv[1].strip()
else:
    RECIPIENT = os.getenv("ALERT_EMAIL_RECIPIENT", "errivanta@gmail.com")

def test_smtp_connection(recipient: str = RECIPIENT):
    print("=" * 60)
    print("[EMAIL TEST] Testing Direct SMTP Email Delivery")
    print(f"Host:      {SMTP_HOST}:{SMTP_PORT}")
    print(f"Sender:    {SMTP_FROM} (Errivanta Platform Mailer)")
    print(f"Recipient: {recipient} (Organization Admin Email)")
    print("=" * 60)

    msg = MIMEMultipart()
    msg["From"] = SMTP_FROM
    msg["To"] = recipient
    msg["Subject"] = "[CRITICAL] Errivanta Incident Alert: High Error Rate Detected"
    
    body = """
======================================================
🚨 ERRIVANTA LIVE INCIDENT ALERT (CRITICAL)
======================================================
Organization: Demo Organization / User Org
Service:      payment-service
Severity:     CRITICAL
Status:       OPEN
Error Rate:   35.2%
Trigger:      Error rate reached 35.2% (exceeded 10.0% critical threshold)

Description:
Service 'payment-service' is experiencing high failure rates in the last 5 minutes.
Recent error: ConnectionRefusedError: Unable to connect to Payment Database pool on port 5432!
======================================================
"""
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        print(f"[SUCCESS] Incident alert email sent successfully to {recipient}")
        return True
    except Exception as e:
        print(f"[FAILED] to send email via SMTP: {e}")
        return False

if __name__ == "__main__":
    test_smtp_connection()
