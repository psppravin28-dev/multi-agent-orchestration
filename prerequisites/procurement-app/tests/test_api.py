"""
Uses an in-memory SQLite DB per test session and overrides the app's
get_session dependency -- the standard FastAPI pattern for testing without
touching the real procurement.db file.
"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.database import get_session
from app.main import app


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def _create_vendor(client, **overrides):
    payload = {"name": "Dell Business", "category": "laptops", "rating": 4.6}
    payload.update(overrides)
    return client.post("/vendors", json=payload).json()


def test_create_and_list_vendor(client):
    _create_vendor(client)
    resp = client.get("/vendors", params={"category": "laptops"})
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["name"] == "Dell Business"


def test_compliance_clears_small_spend(client):
    vendor = _create_vendor(client)
    resp = client.post("/compliance/check", json={"vendor_id": vendor["id"], "amount_usd": 500})
    assert resp.json()["cleared"] is True


def test_compliance_flags_large_spend(client):
    vendor = _create_vendor(client)
    resp = client.post("/compliance/check", json={"vendor_id": vendor["id"], "amount_usd": 60_000})
    assert resp.json()["cleared"] is False
    assert "CFO" in resp.json()["reason"]


def test_compliance_flags_sanctioned_vendor(client):
    vendor = _create_vendor(client, name="Shady Supplies", on_sanctions_list=True)
    resp = client.post("/compliance/check", json={"vendor_id": vendor["id"], "amount_usd": 100})
    assert resp.json()["cleared"] is False
    assert "restricted" in resp.json()["reason"]


def test_purchase_order_issued_immediately_when_cleared(client):
    vendor = _create_vendor(client)
    resp = client.post("/purchase-orders", json={"vendor_id": vendor["id"], "amount_usd": 500})
    assert resp.status_code == 201
    assert resp.json()["status"] == "issued"


def test_purchase_order_requires_approval_when_flagged(client):
    vendor = _create_vendor(client)
    po = client.post("/purchase-orders", json={"vendor_id": vendor["id"], "amount_usd": 60_000}).json()
    assert po["status"] == "pending_approval"

    approve_resp = client.post(f"/purchase-orders/{po['id']}/approve", json={"approved_by": "cfo@example.com"})
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "issued"
    assert approve_resp.json()["approved_by"] == "cfo@example.com"


def test_cannot_approve_a_po_twice(client):
    vendor = _create_vendor(client)
    po = client.post("/purchase-orders", json={"vendor_id": vendor["id"], "amount_usd": 60_000}).json()
    client.post(f"/purchase-orders/{po['id']}/approve", json={"approved_by": "cfo@example.com"})
    second = client.post(f"/purchase-orders/{po['id']}/approve", json={"approved_by": "cfo@example.com"})
    assert second.status_code == 409


def test_contract_lookup_for_vendor(client):
    vendor = _create_vendor(client)
    client.post(
        "/contracts",
        json={"vendor_id": vendor["id"], "liability_cap_usd": 250_000, "payment_terms": "Net-30"},
    )
    resp = client.get(f"/vendors/{vendor['id']}/contract")
    assert resp.status_code == 200
    assert resp.json()["payment_terms"] == "Net-30"
