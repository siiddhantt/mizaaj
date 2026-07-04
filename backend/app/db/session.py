from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url.replace("+asyncpg", "+psycopg"), pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
