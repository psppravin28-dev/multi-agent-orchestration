"""
Postgres only. No SQLite fallback — one database, no ambiguity about which
environment you're pointed at. Requires docker-compose (or a native
Postgres install) to be running; see README for setup.
"""
import os
from typing import Generator

from dotenv import load_dotenv
from sqlmodel import Session, SQLModel, create_engine

load_dotenv()  # reads .env in the current working directory, if present

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://procurement:procurement@localhost:5432/procurement",
)

engine = create_engine(DATABASE_URL)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
