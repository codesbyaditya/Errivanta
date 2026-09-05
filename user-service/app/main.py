from contextlib import asynccontextmanager
from typing import List
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db, Base, engine
from app.models import User
from app.schemas import UserCreate, UserResponse, HealthResponse
from errivanta import Errivanta


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Errivanta User Service",
    description="A user management microservice integrated with Errivanta monitoring.",
    version="1.0.0",
    lifespan=lifespan,
)

# Attach Errivanta SDK Monitoring Middleware
monitor = Errivanta(
    service_name="user-service",
    api_key="sw_demo_12345",
    monitoring_url="http://localhost:8001",
)
monitor.init_app(app)


# 1. Health Check
@app.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check",
    tags=["System"],
)
def health_check():
    return {"status": "healthy", "service": "user-service"}


# 2. Create User
@app.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user",
    tags=["Users"],
)
def create_user(user_in: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(
        (User.username == user_in.username) | (User.email == user_in.email)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered",
        )

    db_user = User(
        username=user_in.username,
        email=user_in.email,
        full_name=user_in.full_name,
        role=user_in.role or "developer",
        status="ACTIVE",
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


# 3. List Users
@app.get(
    "/users",
    response_model=List[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="List all users",
    tags=["Users"],
)
def list_users(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    return db.query(User).offset(skip).limit(limit).all()


# 4. Get User by ID
@app.get(
    "/users/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get user details by ID",
    tags=["Users"],
)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found",
        )
    return user


# 5. Simulate Failure (For real failure demonstration)
@app.post(
    "/users/simulate-failure",
    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    summary="Simulate an internal failure in user-service",
    tags=["Testing"],
)
def simulate_failure():
    """Simulates an unhandled database connection timeout or exception."""
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="CRITICAL: Simulated database timeout in user-service",
    )
