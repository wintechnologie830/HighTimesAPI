"""
This sets up OUR OWN database — completely separate from pos.db — where
all points/loyalty data is stored. Aronium never sees or touches this file.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

engine = create_engine(
    f"sqlite:///{settings.loyalty_db_path}",
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    # Creates tables in loyalty.db (our own file) if they don't exist yet.
    from app import models  # noqa: F401  (ensures models are registered)
    Base.metadata.create_all(bind=engine)
