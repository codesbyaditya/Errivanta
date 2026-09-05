import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from app.models import Incident, IncidentSeverity, IncidentStatus, Service

logger = logging.getLogger("servicewatch.incidents")


from app.notifications.manager import notification_manager


class IncidentEngine:
    """
    Evaluates service error metrics against configurable thresholds and creates/updates incidents.
    Enforces strict deduplication so existing open issues are updated rather than duplicated.
    """

    WARNING_THRESHOLD_PERCENT = 5.0
    CRITICAL_THRESHOLD_PERCENT = 10.0

    @classmethod
    def evaluate_service_health_and_incidents(
        cls,
        db: Session,
        service_id: int,
        service_name: str,
        metrics: dict,
        latest_endpoint: Optional[str] = None,
        latest_error: Optional[str] = None,
    ) -> Optional[Incident]:
        error_rate = metrics.get("error_rate", 0.0)
        total_requests = metrics.get("total_requests", 0)

        # Require at least 1 request before triggering
        if total_requests == 0:
            return None

        now = datetime.now(timezone.utc)

        # 1. Determine if condition violates thresholds
        severity = None
        trigger_msg = None

        if error_rate > cls.CRITICAL_THRESHOLD_PERCENT:
            severity = IncidentSeverity.CRITICAL.value
            trigger_msg = f"Error rate reached {error_rate}% (exceeded {cls.CRITICAL_THRESHOLD_PERCENT}% critical threshold)"
        elif error_rate >= cls.WARNING_THRESHOLD_PERCENT:
            severity = IncidentSeverity.WARNING.value
            trigger_msg = f"Error rate reached {error_rate}% (exceeded {cls.WARNING_THRESHOLD_PERCENT}% warning threshold)"

        # 2. Check for active OPEN incident for this service (Deduplication)
        open_incident = (
            db.query(Incident)
            .filter(
                Incident.service_id == service_id,
                Incident.status == IncidentStatus.OPEN.value,
            )
            .first()
        )

        service = db.query(Service).filter(Service.id == service_id).first()

        if severity:
            error_details = latest_error or "Multiple failures detected"
            description = (
                f"Service '{service_name}' is experiencing high error rates ({error_rate}%).\n"
                f"Recent error: {error_details}"
            )

            if open_incident:
                # Update existing incident (Deduplication)
                open_incident.error_rate = error_rate
                open_incident.severity = severity
                open_incident.trigger_condition = trigger_msg
                open_incident.last_updated_at = now
                open_incident.description = description
                if latest_endpoint:
                    open_incident.relevant_endpoint = latest_endpoint
                db.commit()
                db.refresh(open_incident)
                logger.info(f"[Incidents] Updated ongoing Incident #{open_incident.id} for {service_name}")

                # Dispatch notifications (manager handles anti-spam check)
                if service:
                    notification_manager.dispatch_incident_notification(
                        db=db,
                        incident=open_incident,
                        service=service,
                        organization=service.organization,
                    )
                return open_incident
            else:
                # Create brand new incident
                new_incident = Incident(
                    service_id=service_id,
                    service_name=service_name,
                    severity=severity,
                    status=IncidentStatus.OPEN.value,
                    trigger_condition=trigger_msg,
                    error_rate=error_rate,
                    relevant_endpoint=latest_endpoint,
                    description=description,
                    started_at=now,
                    last_updated_at=now,
                )
                db.add(new_incident)
                db.commit()
                db.refresh(new_incident)
                logger.warning(f"[Incidents] Created NEW Incident #{new_incident.id} for {service_name} ({severity})")

                # Dispatch notifications (manager handles anti-spam check)
                if service:
                    notification_manager.dispatch_incident_notification(
                        db=db,
                        incident=new_incident,
                        service=service,
                        organization=service.organization,
                    )
                return new_incident

        return open_incident

    @classmethod
    def resolve_incident(cls, db: Session, incident_id: int) -> Optional[Incident]:
        """Manually or automatically resolves an open incident."""
        incident = db.query(Incident).filter(Incident.id == incident_id).first()
        if incident and incident.status == IncidentStatus.OPEN.value:
            incident.status = IncidentStatus.RESOLVED.value
            incident.resolved_at = datetime.now(timezone.utc)
            incident.last_updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(incident)
            logger.info(f"[Incidents] Resolved Incident #{incident.id} for {incident.service_name}")
        return incident
