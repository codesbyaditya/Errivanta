import json
import logging
from typing import Optional
import requests

from app.config import settings
from app.models import Incident, Service, Organization
from app.notifications.base import BaseNotifier

logger = logging.getLogger("servicewatch.notifications.slack")


class SlackNotifier(BaseNotifier):
    """
    Sends rich Slack alert cards when critical incidents are detected.
    Automatically operates in mock/development mode if SLACK_WEBHOOK_URL is unset.
    """

    def send_incident_alert(
        self,
        incident: Incident,
        service: Service,
        organization: Optional[Organization] = None,
    ) -> bool:
        org_name = organization.name if organization else "Default Org"
        icon = "🔴" if incident.severity == "CRITICAL" else "🟡"

        slack_text = (
            f"{icon} *{incident.severity} INCIDENT*\n\n"
            f"*Organization:* {org_name}\n"
            f"*Service:* `{service.name}`\n"
            f"*Error Rate:* *{incident.error_rate}%*\n"
            f"*Status:* `{incident.status}`\n"
            f"*Trigger:* {incident.trigger_condition}\n"
            f"*Time:* {incident.started_at.strftime('%Y-%m-%d %H:%M:%S UTC') if incident.started_at else 'Just now'}"
        )

        payload = {
            "text": f"{icon} Errivanta Alert: {service.name} ({incident.severity})",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"{icon} Errivanta Incident Alert",
                        "emoji": True,
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Service:*\n`{service.name}`"},
                        {"type": "mrkdwn", "text": f"*Severity:*\n*{incident.severity}*"},
                        {"type": "mrkdwn", "text": f"*Error Rate:*\n`{incident.error_rate}%`"},
                        {"type": "mrkdwn", "text": f"*Status:*\n`{incident.status}`"},
                    ],
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Details:*\n{incident.trigger_condition}",
                    },
                },
            ],
        }

        # Check if webhook URL is configured
        if not settings.SLACK_WEBHOOK_URL:
            logger.info(
                f"[SlackNotifier MOCK] Slack Webhook Message:\n"
                f"{slack_text}"
            )
            return True

        # Send HTTP POST to Slack Webhook
        try:
            res = requests.post(
                settings.SLACK_WEBHOOK_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=5,
            )
            if res.status_code == 200:
                logger.info(f"[SlackNotifier] Successfully posted alert to Slack for incident #{incident.id}")
                return True
            else:
                logger.error(
                    f"[SlackNotifier] Slack webhook responded with HTTP {res.status_code}: {res.text}"
                )
                return False
        except Exception as e:
            logger.error(f"[SlackNotifier] Exception sending alert to Slack for incident #{incident.id}: {e}")
            return False
