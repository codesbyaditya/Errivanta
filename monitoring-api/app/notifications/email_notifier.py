import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from app.config import settings
from app.models import Incident, Service, Organization
from app.notifications.base import BaseNotifier

logger = logging.getLogger("servicewatch.notifications.email")


class EmailNotifier(BaseNotifier):
    """
    Sends email alerts for critical service incidents.
    Automatically uses clean mock/development mode if SMTP settings are not provided.
    """

    def send_incident_alert(
        self,
        incident: Incident,
        service: Service,
        organization: Optional[Organization] = None,
    ) -> bool:
        org_name = organization.name if organization else "ServiceWatch Platform"
        
        # Dynamically lookup registered admin user emails for this specific organization
        recipients = []
        if organization and hasattr(organization, "users") and organization.users:
            recipients = [u.email for u in organization.users if u.email]
        if not recipients:
            recipients = [settings.ALERT_EMAIL_RECIPIENT]

        subject = f"[{incident.severity}] Errivanta Alert: {service.name} Incident #{incident.id}"
        body_text = f"""
======================================================
ERRIVANTA INCIDENT ALERT ({incident.severity})
======================================================
Organization: {org_name}
Service:      {service.name}
Severity:     {incident.severity}
Status:       {incident.status}
Error Rate:   {incident.error_rate}%
Trigger:      {incident.trigger_condition}
Started At:   {incident.started_at}

Description:
{incident.description}
======================================================
"""

        # Check if real SMTP host is configured
        if not settings.SMTP_HOST or not settings.SMTP_USER:
            logger.info(
                f"[EmailNotifier MOCK] Email Alert to {', '.join(recipients)}:\n"
                f"Subject: {subject}\n"
                f"Service: {service.name} | Error Rate: {incident.error_rate}% | Severity: {incident.severity}"
            )
            return True

        # Send via real SMTP to all organization recipients
        try:
            for recipient in recipients:
                msg = MIMEMultipart()
                msg["From"] = settings.SMTP_FROM_EMAIL
                msg["To"] = recipient
                msg["Subject"] = subject
                msg.attach(MIMEText(body_text, "plain"))

                with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
                    server.starttls()
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                    server.send_message(msg)

                logger.info(f"[EmailNotifier] Successfully sent email alert to {recipient} for incident #{incident.id}")
            return True
        except Exception as e:
            logger.error(f"[EmailNotifier] Failed to send email alert for incident #{incident.id}: {e}")
            return False
