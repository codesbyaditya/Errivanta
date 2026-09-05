import logging
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Incident, Service, Organization
from app.notifications.base import BaseNotifier
from app.notifications.email_notifier import EmailNotifier
from app.notifications.slack_notifier import SlackNotifier

logger = logging.getLogger("servicewatch.notifications")


class NotificationManager:
    """
    Manages dispatching incident notifications across all channels (Email, Slack).
    Enforces anti-spam notification rules and ensures isolated error handling.
    """

    def __init__(self, notifiers: Optional[List[BaseNotifier]] = None):
        self.notifiers = notifiers or [
            EmailNotifier(),
            SlackNotifier(),
        ]

    def should_notify(self, incident: Incident) -> bool:
        """
        Notification rule:
        - Must be enabled in settings.
        - Severity must be CRITICAL (or escalating to CRITICAL).
        - Ongoing OPEN incidents must not repeatedly send notifications.
        """
        if not settings.NOTIFICATIONS_ENABLED:
            return False

        if incident.severity != "CRITICAL":
            return False

        # If already notified at CRITICAL level for this ongoing OPEN incident, prevent spam
        if (
            incident.last_notified_severity == "CRITICAL"
            and incident.status == "OPEN"
        ):
            logger.debug(
                f"[NotificationManager] Suppressing duplicate notification for ongoing Incident #{incident.id}"
            )
            return False

        return True

    def dispatch_incident_notification(
        self,
        db: Session,
        incident: Incident,
        service: Service,
        organization: Optional[Organization] = None,
    ) -> bool:
        """
        Evaluates spam rules and dispatches alerts to all configured channels.
        Updates the incident record to remember the notification state.
        """
        if not self.should_notify(incident):
            return False

        logger.info(
            f"[NotificationManager] Dispatching CRITICAL incident notifications for {service.name} (Incident #{incident.id})"
        )

        all_success = True
        for notifier in self.notifiers:
            try:
                success = notifier.send_incident_alert(incident, service, organization)
                if not success:
                    all_success = False
            except Exception as e:
                logger.error(
                    f"[NotificationManager] Unexpected notifier exception ({notifier.__class__.__name__}): {e}"
                )
                all_success = False

        # Mark incident as notified to prevent duplicate spam
        now = datetime.now(timezone.utc)
        incident.last_notified_severity = incident.severity
        incident.notified_at = now
        try:
            db.commit()
            db.refresh(incident)
        except Exception as e:
            logger.error(f"[NotificationManager] Failed to persist notified_at for Incident #{incident.id}: {e}")

        return all_success


# Global default instance
notification_manager = NotificationManager()
