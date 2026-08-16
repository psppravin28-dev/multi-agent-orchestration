from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.database import get_session
from app.models import Vendor
from app.schemas import COMPLIANCE_FLAG_THRESHOLD_USD, ComplianceCheckRequest, ComplianceCheckResult

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.post("/check", response_model=ComplianceCheckResult)
def check_compliance(payload: ComplianceCheckRequest, session: Session = Depends(get_session)):
    """This is what the compliance agent's check_compliance_policy tool
    calls. Real policy logic (sanctions screening, delegation-of-authority
    tiers) belongs here, in the system of record -- not hardcoded in the
    agent's prompt, where it can't be audited or version-controlled the
    same way."""
    vendor = session.get(Vendor, payload.vendor_id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    if vendor.on_sanctions_list:
        return ComplianceCheckResult(cleared=False, reason=f"{vendor.name} is on the restricted vendor list.")

    if payload.amount_usd >= COMPLIANCE_FLAG_THRESHOLD_USD:
        return ComplianceCheckResult(
            cleared=False,
            reason=f"Spend of ${payload.amount_usd:,.0f} requires CFO sign-off per policy P-204.",
        )

    return ComplianceCheckResult(
        cleared=True,
        reason=f"{vendor.name} not restricted; spend within delegated authority.",
    )
