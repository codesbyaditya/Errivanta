from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from app.models import PaymentStatus


# Schema for creating a payment (Request Body)
class PaymentCreate(BaseModel):
    user_id: int = Field(..., gt=0, description="Unique ID of the user initiating the payment")
    amount: float = Field(..., gt=0, description="Payment amount (must be greater than 0)")
    currency: str = Field(default="INR", min_length=3, max_length=5, description="Currency code, e.g., INR, USD")


# Schema for returning payment details (Response Body)
class PaymentResponse(BaseModel):
    id: int
    user_id: int
    amount: float
    currency: str
    status: PaymentStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Schema for health check endpoint
class HealthResponse(BaseModel):
    status: str = "healthy"
