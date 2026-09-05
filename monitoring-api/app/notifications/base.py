from abc import ABC, abstractmethod
from typing import Optional
from app.models import Incident, Service, Organization


class BaseNotifier(ABC):
    """
    Abstract interface for incident notification dispatchers.
    Implementations must safely handle network failures without raising exceptions to callers.
    """

    @abstractmethod
    def send_incident_alert(
        self,
        incident: Incident,
        service: Service,
        organization: Optional[Organization] = None,
    ) -> bool:
        """
        Dispatches an incident alert. Returns True if successfully sent/logged, False otherwise.
        """
        pass
