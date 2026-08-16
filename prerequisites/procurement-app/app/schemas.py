"""
Schemas that aren't database tables -- request bodies and computed response
shapes. Kept separate from models.py so it's obvious which classes SQLModel
persists and which are just wire format.
"""
from typing import Optional

from pydantic import BaseModel

# Spend at or above this is flagged and requires PO approval before issuing.
# A policy service in a real system; a constant here so it's visible.
COMPLIANCE_FLAG_THRESHOLD_USD = 50_000


class VendorCreate(BaseModel):
    name: str
    category: str
    rating: float = 4.0
    contact_email: Optional[str] = None
    on_sanctions_list: bool = False


class ContractCreate(BaseModel):
    vendor_id: int
    payment_terms: str = "Net-30"
    term_months: int = 12
    liability_cap_usd: float
    auto_renewal: bool = True


class ComplianceCheckRequest(BaseModel):
    vendor_id: int
    amount_usd: float


class ComplianceCheckResult(BaseModel):
    cleared: bool
    reason: str


class PurchaseOrderCreate(BaseModel):
    vendor_id: int
    amount_usd: float
    requested_by: Optional[str] = None


class PurchaseOrderApprove(BaseModel):
    approved_by: str
