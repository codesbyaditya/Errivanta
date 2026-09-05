import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Float, String, DateTime
from app.database import Base


class OrderStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    customer_name = Column(String(100), nullable=False)
    item_count = Column(Integer, nullable=False, default=1)
    total_amount = Column(Float, nullable=False)
    status = Column(String(20), nullable=False, default=OrderStatus.CONFIRMED.value)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Order(id={self.id}, customer={self.customer_name}, total={self.total_amount})>"
