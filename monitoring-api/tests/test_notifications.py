import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Organization, Service, ApiKey, Incident, IncidentSeverity, IncidentStatus
from app.notifications.base import BaseNotifier
from app.notifications.email_notifier import EmailNotifier
from app.notifications.slack_notifier import SlackNotifier
from app.notifications.manager import NotificationManager
from app.incident_engine import IncidentEngine

from sqlalchemy.pool import StaticPool

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


class MockFailingNotifier(BaseNotifier):
    def send_incident_alert(self, incident, service, organization=None):
        raise RuntimeError("Simulated network outage to Slack/Email provider")


def test_email_and_slack_mock_notifiers():
    email_notifier = EmailNotifier()
    slack_notifier = SlackNotifier()

    org = Organization(name="Alert Test Org")
    service = Service(name="payment-service", organization_id=1)
    incident = Incident(
        id=101,
        service_id=1,
        service_name="payment-service",
        severity="CRITICAL",
        status="OPEN",
        trigger_condition="Error rate reached 25%",
        error_rate=25.0,
        description="High 500 error spike",
        started_at=datetime.now(timezone.utc),
    )

    assert email_notifier.send_incident_alert(incident, service, org) is True
    assert slack_notifier.send_incident_alert(incident, service, org) is True


def test_notification_manager_anti_spam():
    db = TestingSessionLocal()
    try:
        org = Organization(name="Spam Test Org")
        db.add(org)
        db.commit()
        db.refresh(org)

        service = Service(name="order-service", organization_id=org.id)
        db.add(service)
        db.commit()
        db.refresh(service)

        incident = Incident(
            service_id=service.id,
            service_name="order-service",
            severity="CRITICAL",
            status="OPEN",
            trigger_condition="Critical error spike",
            error_rate=15.0,
            started_at=datetime.now(timezone.utc),
            last_updated_at=datetime.now(timezone.utc),
        )
        db.add(incident)
        db.commit()
        db.refresh(incident)

        manager = NotificationManager()

        # 1. First trigger -> Should send notification
        first_dispatch = manager.dispatch_incident_notification(db, incident, service, org)
        assert first_dispatch is True
        assert incident.last_notified_severity == "CRITICAL"
        assert incident.notified_at is not None

        # 2. Second trigger on ongoing OPEN incident -> Anti-spam must suppress
        second_dispatch = manager.dispatch_incident_notification(db, incident, service, org)
        assert second_dispatch is False

        # 3. Resolve incident
        IncidentEngine.resolve_incident(db, incident.id)
        assert incident.status == "RESOLVED"

    finally:
        db.close()


def test_notifier_exception_does_not_crash_manager():
    db = TestingSessionLocal()
    try:
        org = Organization(name="Fault Tolerant Org")
        db.add(org)
        db.commit()
        db.refresh(org)

        service = Service(name="user-service", organization_id=org.id)
        db.add(service)
        db.commit()
        db.refresh(service)

        incident = Incident(
            service_id=service.id,
            service_name="user-service",
            severity="CRITICAL",
            status="OPEN",
            trigger_condition="Simulated crash",
            error_rate=30.0,
            started_at=datetime.now(timezone.utc),
            last_updated_at=datetime.now(timezone.utc),
        )
        db.add(incident)
        db.commit()
        db.refresh(incident)

        # Notification manager with a broken notifier
        manager = NotificationManager(notifiers=[MockFailingNotifier()])

        # Must not raise exception
        result = manager.dispatch_incident_notification(db, incident, service, org)
        assert result is False
    finally:
        db.close()
