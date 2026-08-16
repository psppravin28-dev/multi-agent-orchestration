"""
Tests run against real Postgres (TEST_DATABASE_URL), not a SQLite stand-in
-- catches Postgres-specific behavior (constraint enforcement, type
coercion) that SQLite silently lets slide.

Isolation strategy: one connection + one outer transaction per test,
with the app's Session bound to that connection via
join_transaction_mode="create_savepoint". When router code calls
session.commit() (as it does in normal request handling), SQLAlchemy
commits a SAVEPOINT, not the real transaction -- so the outer
transaction.rollback() after each test fully undoes everything the test
did, including writes the app itself committed. Verified against a live
Postgres instance before this was written, not assumed.
"""
import os

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.database import get_session
from app.main import app

load_dotenv()

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://procurement:procurement@localhost:5432/procurement_test",
)

engine = create_engine(TEST_DATABASE_URL)


@pytest.fixture(scope="session", autouse=True)
def _schema():
    """Create tables once for the whole test run, drop once at the end.
    Individual tests get a clean slate via the transaction rollback below,
    not by recreating tables per test -- that would be far slower."""
    SQLModel.metadata.create_all(engine)
    yield
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="session")
def session_fixture():
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
