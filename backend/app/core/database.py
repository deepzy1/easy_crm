from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    get_settings().database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=5,
    pool_timeout=10,
    pool_recycle=1800,
    connect_args={
        "connect_timeout": 5,
        "options": "-c statement_timeout=15000 -c idle_in_transaction_session_timeout=180000",
    },
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db():
    with SessionLocal() as session:
        yield session
