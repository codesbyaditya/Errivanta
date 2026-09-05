import os
import sys

# Ensure monitoring-api is in sys.path
sys.path.insert(0, os.path.abspath('monitoring-api'))

from datetime import datetime, timezone
from app.config import settings
from app.models import Incident, Service, Organization, User
from app.notifications.manager import notification_manager
from app.database import SessionLocal

print("="*60)
print("SERVICEWATCH NOTIFICATIONS TEST RUNNER")
print("="*60)
print(f"Notifications Enabled: {settings.NOTIFICATIONS_ENABLED}")
print(f"Slack Webhook URL:     {settings.SLACK_WEBHOOK_URL or '(Mock Mode Active)'}")
print(f"SMTP Host:             {settings.SMTP_HOST or '(Mock Mode Active)'}")
print(f"SMTP User:             {settings.SMTP_USER or '(Mock Mode Active)'}")
print(f"Recipient Fallback:    {settings.ALERT_EMAIL_RECIPIENT}")
print("="*60)

db = SessionLocal()
try:
    # Use existing or create test org & service
    org = db.query(Organization).first()
    if not org:
        org = Organization(name="Demo Organization")
        db.add(org)
        db.commit()
        db.refresh(org)

    service = db.query(Service).filter(Service.organization_id == org.id).first()
    if not service:
        service = Service(name="payment-service", organization_id=org.id)
        db.add(service)
        db.commit()
        db.refresh(service)

    test_incident = Incident(
        service_id=service.id,
        service_name=service.name,
        severity="CRITICAL",
        status="OPEN",
        trigger_condition="Error rate reached 24.5% (Threshold >10%)",
        error_rate=24.5,
        description="Automated notification delivery test from ServiceWatch.",
        started_at=datetime.now(timezone.utc),
        last_updated_at=datetime.now(timezone.utc),
    )
    db.add(test_incident)
    db.commit()
    db.refresh(test_incident)

    print("\nDispatching test incident alert across all channels (Email & Slack)...")
    success = notification_manager.dispatch_incident_notification(
        db=db,
        incident=test_incident,
        service=service,
        organization=org,
    )
    print("\n" + "="*60)
    if success:
        print("[SUCCESS] Notification dispatched successfully!")
    else:
        print("[INFO] Notification completed in Mock Mode (or check credentials).")
    print("="*60)
finally:
    db.close()
