from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from app.models import OrderStatus


class OrderCreate(BaseModel):
    customer_name: str = Field(..., min_length=1, description="Customer full name")
    item_count: int = Field(default=1, gt=0, description="Total number of items")
    total_amount: float = Field(..., gt=0, description="Order total value")


class OrderResponse(BaseModel):
    id: int
    customer_name: str
    item_count: int
    total_amount: float
    status: OrderStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HealthResponse(BaseModel):
    status: str = "healthy"
    service: str = "order-service"
