import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

logger = logging.getLogger("order.database")

def create_db_engine():
    connect_args = {}
    db_url = settings.DATABASE_URL

    if db_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        return create_engine(db_url, connect_args=connect_args, echo=False)

    try:
        engine = create_engine(db_url, connect_args=connect_args, echo=False)
        with engine.connect() as conn:
            pass
        return engine
    except Exception as exc:
        logger.warning(
            f"[Database] Could not connect to PostgreSQL at '{db_url}' ({exc}). "
            f"Falling back to local SQLite database 'sqlite:///./servicewatch_order.db'."
        )
        return create_engine("sqlite:///./servicewatch_order.db", connect_args={"check_same_thread": False}, echo=False)


engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
