from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db, Base, engine
from app.models import Payment, PaymentStatus
from app.schemas import PaymentCreate, PaymentResponse, HealthResponse
from servicewatch import ServiceWatch

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(
    title="Errivanta Payment Service",
    description="A lightweight payment service for processing and tracking payments.",
    version="1.0.0",
    lifespan=lifespan,
)



# Initialize and attach ServiceWatch monitoring middleware
monitor = ServiceWatch(
    service_name=settings.APP_NAME,
    api_key=settings.SERVICEWATCH_API_KEY,
    monitoring_url=settings.SERVICEWATCH_URL,
)
monitor.init_app(app)




# 1. Health Check Endpoint
@app.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check endpoint",
    tags=["System"]
)
def health_check():
    """Returns the service health status."""
    return {"status": "healthy"}


# 2. Create Payment Endpoint
@app.post(
    "/payments",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new payment",
    tags=["Payments"]
)
def create_payment(payment_in: PaymentCreate, db: Session = Depends(get_db)):
    """
    Creates a new payment record in the database.
    - Validates user_id, amount, and currency.
    - Stores the record in PostgreSQL.
    - Returns the created payment object.
    """
    db_payment = Payment(
        user_id=payment_in.user_id,
        amount=payment_in.amount,
        currency=payment_in.currency.upper(),
        status=PaymentStatus.SUCCESS.value
    )
    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)
    return db_payment


# 3. Get Payment by ID Endpoint
@app.get(
    "/payments/{payment_id}",
    response_model=PaymentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get payment details by ID",
    tags=["Payments"]
)
def get_payment(payment_id: int, db: Session = Depends(get_db)):
    """
    Retrieves a payment by its unique ID.
    - Returns 404 if the payment does not exist.
    """
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment with ID {payment_id} not found"
        )
    return payment
