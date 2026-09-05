from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db, Base, engine
from app.models import Order, OrderStatus
from app.schemas import OrderCreate, OrderResponse, HealthResponse
from errivanta import Errivanta


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Errivanta Order Service",
    description="A lightweight order processing microservice integrated with Errivanta monitoring.",
    version="1.0.0",
    lifespan=lifespan,
)

# Attach Errivanta SDK Monitoring Middleware
monitor = Errivanta(
    service_name="order-service",
    api_key="sw_demo_12345",
    monitoring_url="http://localhost:8001",
)
monitor.init_app(app)


# 1. Health Endpoint
@app.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check",
    tags=["System"],
)
def health_check():
    return {"status": "healthy", "service": "order-service"}


# 2. Create Order
@app.post(
    "/orders",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new order",
    tags=["Orders"],
)
def create_order(order_in: OrderCreate, db: Session = Depends(get_db)):
    db_order = Order(
        customer_name=order_in.customer_name,
        item_count=order_in.item_count,
        total_amount=order_in.total_amount,
        status=OrderStatus.CONFIRMED.value,
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    return db_order


# 3. Get Order by ID
@app.get(
    "/orders/{order_id}",
    response_model=OrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Get order by ID",
    tags=["Orders"],
)
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order with ID {order_id} not found",
        )
    return order
