"""Motor de base de datos y sesión (SQLAlchemy 2.0)."""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import DATABASE_URL

# check_same_thread=False permite usar la misma conexión desde FastAPI
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Base para todos los modelos ORM."""
    pass


def get_session() -> Session:
    """Generador de sesión para inyectar en los endpoints."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
