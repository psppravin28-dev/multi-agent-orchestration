"""
SQLite for local dev -- zero setup, file-based, good enough for the whole
learning track. Swap DATABASE_URL for a Postgres URL when this moves toward
a real deployment; nothing else in the app needs to change because we only
use SQLModel's engine-agnostic API.
"""
import os
from typing import Generator

from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = os.environ.get("PROCUREMENT_DB_URL", "sqlite:///./procurement.db")

# check_same_thread=False is SQLite-specific and required because FastAPI
# can serve a request on a different thread than the one that created the
# connection. Not needed / not present for Postgres.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
