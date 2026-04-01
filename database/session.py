from collections.abc import Generator
import logging
from sqlmodel import Session, SQLModel, create_engine

from core.config import get_settings


settings = get_settings()

engine = create_engine(str(settings.DATABASE_URL), echo=settings.DEBUG)

def get_session() -> Generator[Session, None, None]:
    try:
        with Session(engine) as session:
            yield session
    except Exception as e:
        logging.error(f"Error getting session: {e}")
        raise e
    finally:
        session.close()
