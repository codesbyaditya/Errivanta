import logging
import smtplib
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List

from app.config import settings
from app.models import Incident, Service, Organization
from app.notifications.base import BaseNotifier

logger = logging.getLogger("servicewatch.notifications.email")


class EmailNotifier(BaseNotifier):
    """
    Sends email alerts for critical service incidents to registered organization users.
    Executes in a background thread to ensure HTTP telemetry ingestion is never blocked.
    """

    def send_incident_alert(
        self,
        incident: Incident,
        service: Service,
        organization: Optional[Organization] = None,
    ) -> bool:
        org_name = organization.name if organization else "Errivanta Monitored Organization"
        from_email = (settings.SMTP_FROM_EMAIL or "errivanta@gmail.com").strip().lower()

        # Dynamically lookup registered admin user emails for this specific organization
        recipients: List[str] = []
        if organization and hasattr(organization, "users") and organization.users:
            for u in organization.users:
                if u.email:
                    email_cleaned = u.email.strip()
                    if email_cleaned.lower() != from_email and email_cleaned not in recipients:
                        recipients.append(email_cleaned)

        # Fallback to configured alert recipient if none found or all matched sender
        if not recipients:
            fallback = (settings.ALERT_EMAIL_RECIPIENT or "").strip()
            if fallback and fallback.lower() != from_email:
                recipients.append(fallback)

        if not recipients:
            logger.warning(
                f"[EmailNotifier] No valid recipient email found for organization '{org_name}' "
                f"(Sender is {from_email}; recipient must not match sender)."
            )
            return False

        # Extract incident information safely before launching background thread
        incident_id = incident.id
        severity = incident.severity
        status = incident.status
        error_rate = incident.error_rate
        trigger_condition = incident.trigger_condition
        started_at = str(incident.started_at)
        description = incident.description or "High error rate detected."
        service_name = service.name

        # Check if real SMTP host is configured
        if not settings.SMTP_HOST or not settings.SMTP_USER:
            logger.info(
                f"[EmailNotifier MOCK] Email Alert to {', '.join(recipients)}:\n"
                f"Subject: [{severity}] Errivanta Incident Alert: {service_name} ({error_rate}% Error Rate)\n"
                f"Service: {service_name} | Error Rate: {error_rate}% | Severity: {severity}"
            )
            return True

        def _deliver_email_task():
            subject = f"[{severity}] Errivanta Incident Alert: {service_name} ({error_rate}% Error Rate)"
            plain_body = f"""======================================================
🚨 ERRIVANTA LIVE INCIDENT ALERT ({severity})
======================================================
Organization: {org_name}
Service:      {service_name}
Severity:     {severity}
Status:       {status}
Error Rate:   {error_rate}%
Trigger:      {trigger_condition}
Started At:   {started_at}

Description:
{description}

View Live Telemetry:
https://errivanta.onrender.com
======================================================
"""
            html_body = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0f172a; color: #f8fafc; margin: 0; padding: 24px; }}
    .container {{ max-width: 600px; margin: 0 auto; background-color: #1e293b; border: 1px solid #dc2626; border-radius: 12px; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
    .header {{ background: linear-gradient(135deg, #dc2626, #991b1b); padding: 24px; color: #ffffff; text-align: center; }}
    .header h1 {{ margin: 0; font-size: 22px; letter-spacing: 0.5px; }}
    .badge {{ display: inline-block; background-color: #fecaca; color: #991b1b; font-weight: bold; font-size: 12px; padding: 4px 10px; border-radius: 9999px; text-transform: uppercase; margin-top: 8px; }}
    .content {{ padding: 24px; }}
    .metric-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 20px 0; }}
    .metric-card {{ background-color: #0f172a; padding: 14px; border-radius: 8px; border: 1px solid #334155; }}
    .metric-label {{ font-size: 11px; text-transform: uppercase; color: #94a3b8; margin-bottom: 4px; }}
    .metric-value {{ font-size: 18px; font-weight: bold; color: #f8fafc; }}
    .metric-value.danger {{ color: #ef4444; }}
    .desc-box {{ background-color: #0f172a; border-left: 4px solid #ef4444; padding: 16px; border-radius: 4px; font-family: monospace; font-size: 13px; color: #cbd5e1; margin-top: 16px; white-space: pre-wrap; }}
    .footer {{ padding: 20px; text-align: center; font-size: 12px; color: #64748b; border-top: 1px solid #334155; }}
    .btn {{ display: inline-block; background-color: #3b82f6; color: #ffffff; text-decoration: none; padding: 10px 20px; border-radius: 6px; font-weight: 600; margin-top: 16px; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>🚨 Critical Incident Detected</h1>
      <span class="badge">{severity}</span>
    </div>
    <div class="content">
      <p style="margin: 0; font-size: 15px; color: #cbd5e1;">
        The Errivanta Telemetry Engine has identified an active service outage for <strong>{service_name}</strong> under organization <strong>{org_name}</strong>.
      </p>
      <div class="metric-grid">
        <div class="metric-card">
          <div class="metric-label">Monitored Service</div>
          <div class="metric-value">{service_name}</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">Current Error Rate</div>
          <div class="metric-value danger">{error_rate}%</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">Incident Status</div>
          <div class="metric-value">{status}</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">Trigger Condition</div>
          <div class="metric-value" style="font-size: 13px;">{trigger_condition}</div>
        </div>
      </div>
      <div class="desc-box">
        {description}
      </div>
      <div style="text-align: center;">
        <a href="https://errivanta.onrender.com" class="btn">Open Telemetry Dashboard</a>
      </div>
    </div>
    <div class="footer">
      Sent automatically by Errivanta Telemetry & Incident Platform. Incident ID #{incident_id}
    </div>
  </div>
</body>
</html>
"""
            try:
                for recipient in recipients:
                    msg = MIMEMultipart("alternative")
                    msg["From"] = settings.SMTP_FROM_EMAIL
                    msg["To"] = recipient
                    msg["Subject"] = subject
                    msg.attach(MIMEText(plain_body, "plain"))
                    msg.attach(MIMEText(html_body, "html"))

                    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=12) as server:
                        server.starttls()
                        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                        server.send_message(msg)

                    logger.info(f"[EmailNotifier] Successfully sent email alert to {recipient} for Incident #{incident_id}")
            except Exception as e:
                logger.error(f"[EmailNotifier] Failed to send email alert for Incident #{incident_id}: {e}")

        # Dispatch via non-blocking background thread
        threading.Thread(target=_deliver_email_task, daemon=True).start()
        return True

