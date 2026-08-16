"""
SQLModel table definitions. SQLModel = SQLAlchemy tables + Pydantic
validation in one class, which is why request/response schemas below can
reuse these directly instead of duplicating every field.
"""
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Vendor(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    category: str = Field(index=True)
    rating: float = 4.0
    contact_email: Optional[str] = None
    on_sanctions_list: bool = False
    status: str = "active"  # active | inactive


class Contract(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    vendor_id: int = Field(foreign_key="vendor.id", index=True)
    payment_terms: str = "Net-30"
    term_months: int = 12
    liability_cap_usd: float
    auto_renewal: bool = True
    status: str = "active"  # active | expired | terminated
    created_at: datetime = Field(default_factory=utcnow)


class PurchaseOrder(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    po_number: str = Field(index=True, unique=True)
    vendor_id: int = Field(foreign_key="vendor.id", index=True)
    amount_usd: float
    # draft -> pending_approval -> approved -> issued
    #                          \-> rejected
    status: str = "draft"
    requested_by: Optional[str] = None
    compliance_note: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
