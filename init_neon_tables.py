import os
import sys

NEON_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://user:password@localhost:5432/neondb"
)

from datetime import datetime, timezone
from sqlalchemy import create_engine, inspect, text, Column, Integer, String, Float, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto")
engine = create_engine(NEON_URL, pool_pre_ping=True)
Base = declarative_base()

# Models Definition
class Organization(Base):
    __tablename__ = "organizations"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    services = relationship("Service", back_populates="organization", cascade="all, delete-orphan")

class User(Base):
    __tablename__ = "auth_users"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(150), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=True)
    role = Column(String(50), nullable=False, default="admin")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    organization = relationship("Organization", back_populates="users")

class Service(Base):
    __tablename__ = "services"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    organization = relationship("Organization", back_populates="services")
    api_keys = relationship("ApiKey", back_populates="service", cascade="all, delete-orphan")
    events = relationship("MonitoringEvent", back_populates="service", cascade="all, delete-orphan")
    incidents = relationship("Incident", back_populates="service", cascade="all, delete-orphan")

class ApiKey(Base):
    __tablename__ = "api_keys"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    service_id = Column(Integer, ForeignKey("services.id", ondelete="CASCADE"), nullable=False)
    key = Column(String(128), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False, default="Default Key")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    service = relationship("Service", back_populates="api_keys")

class MonitoringEvent(Base):
    __tablename__ = "monitoring_events"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    service_id = Column(Integer, ForeignKey("services.id", ondelete="CASCADE"), nullable=False, index=True)
    service_name = Column(String(100), nullable=False)
    endpoint = Column(String(255), nullable=False, index=True)
    method = Column(String(10), nullable=False)
    status_code = Column(Integer, nullable=False, index=True)
    response_time_ms = Column(Float, nullable=False)
    error = Column(Text, nullable=True)
    timestamp = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    service = relationship("Service", back_populates="events")

class Incident(Base):
    __tablename__ = "incidents"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    service_id = Column(Integer, ForeignKey("services.id", ondelete="CASCADE"), nullable=False, index=True)
    service_name = Column(String(100), nullable=False)
    severity = Column(String(20), nullable=False, default="CRITICAL")
    status = Column(String(20), nullable=False, default="OPEN", index=True)
    trigger_condition = Column(String(255), nullable=False)
    error_rate = Column(Float, nullable=False)
    relevant_endpoint = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    last_notified_severity = Column(String(20), nullable=True)
    notified_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime, nullable=True)
    service = relationship("Service", back_populates="incidents")

class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    status = Column(String(20), nullable=False, default="CONFIRMED")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    customer_name = Column(String(100), nullable=False)
    item_count = Column(Integer, nullable=False, default=1)
    total_amount = Column(Float, nullable=False)
    status = Column(String(20), nullable=False, default="CONFIRMED")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

class MicroserviceUser(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    full_name = Column(String(100), nullable=True)
    role = Column(String(50), nullable=False, default="developer")
    status = Column(String(20), nullable=False, default="ACTIVE")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

print("1. Creating all tables directly in Neon PostgreSQL...")
Base.metadata.create_all(bind=engine)

print("2. Seeding initial SaaS organization, admin user, and microservices...")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

org = db.query(Organization).filter(Organization.name == "Demo Organization").first()
if not org:
    org = Organization(name="Demo Organization")
    db.add(org)
    db.commit()
    db.refresh(org)

admin_user = db.query(User).filter(User.email == "admin@servicewatch.io").first()
if not admin_user:
    admin_user = User(
        organization_id=org.id,
        email="admin@servicewatch.io",
        hashed_password=pwd_context.hash("password123"),
        full_name="ServiceWatch Admin",
        role="admin",
    )
    db.add(admin_user)
    db.commit()

# Seed Payment Service
pay_svc = db.query(Service).filter(Service.name == "payment-service").first()
if not pay_svc:
    pay_svc = Service(organization_id=org.id, name="payment-service")
    db.add(pay_svc)
    db.commit()
    db.refresh(pay_svc)

pay_key = db.query(ApiKey).filter(ApiKey.key == "sw_demo_payment_key_12345").first()
if not pay_key:
    pay_key = ApiKey(service_id=pay_svc.id, key="sw_demo_payment_key_12345", name="Payment Key", is_active=True)
    db.add(pay_key)
    db.commit()

# Seed Order Service
ord_svc = db.query(Service).filter(Service.name == "order-service").first()
if not ord_svc:
    ord_svc = Service(organization_id=org.id, name="order-service")
    db.add(ord_svc)
    db.commit()
    db.refresh(ord_svc)

ord_key = db.query(ApiKey).filter(ApiKey.key == "sw_demo_order_key_12345").first()
if not ord_key:
    ord_key = ApiKey(service_id=ord_svc.id, key="sw_demo_order_key_12345", name="Order Key", is_active=True)
    db.add(ord_key)
    db.commit()

# Seed User Service
usr_svc = db.query(Service).filter(Service.name == "user-service").first()
if not usr_svc:
    usr_svc = Service(organization_id=org.id, name="user-service")
    db.add(usr_svc)
    db.commit()
    db.refresh(usr_svc)

usr_key = db.query(ApiKey).filter(ApiKey.key == "sw_live_user_service_key").first()
if not usr_key:
    usr_key = ApiKey(service_id=usr_svc.id, key="sw_live_user_service_key", name="User Service Key", is_active=True)
    db.add(usr_key)
    db.commit()

# Seed a sample payment & sample order
sample_payment = Payment(amount=199.99, currency="USD", status="CONFIRMED")
db.add(sample_payment)
sample_order = Order(customer_name="John Doe", item_count=3, total_amount=199.99, status="CONFIRMED")
db.add(sample_order)
db.commit()
db.close()

# Inspect Neon tables
inspector = inspect(engine)
tables = inspector.get_table_names()
print("\n" + "="*60)
print("SUCCESS! All tables and data are now live in Neon PostgreSQL:")
with engine.connect() as conn:
    for t in sorted(tables):
        count = conn.execute(text(f'SELECT count(*) FROM "{t}"')).fetchone()[0]
        print(f"  - Table: {t:<22} | Rows: {count}")
print("="*60)
