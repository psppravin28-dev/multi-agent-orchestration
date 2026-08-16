import hashlib

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.database import get_session
from app.models import PurchaseOrder, Vendor
from app.routers.compliance import check_compliance
from app.schemas import ComplianceCheckRequest, PurchaseOrderApprove, PurchaseOrderCreate

router = APIRouter(prefix="/purchase-orders", tags=["purchase-orders"])


def _generate_po_number(vendor_id: int, amount_usd: float) -> str:
    digest = hashlib.sha1(f"{vendor_id}{amount_usd}{PurchaseOrder.__name__}".encode()).hexdigest()[:6]
    return f"PO-{digest.upper()}"


@router.post("", response_model=PurchaseOrder, status_code=201)
def create_purchase_order(payload: PurchaseOrderCreate, session: Session = Depends(get_session)):
    """This is what the po_generation agent's generate_purchase_order tool
    calls. Compliance is re-checked here, server-side, on the actual amount
    -- never trust the agent's own prior compliance read as authorization to
    write. This is the same principle as re-validating on the server after
    client-side form validation."""
    vendor = session.get(Vendor, payload.vendor_id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    result = check_compliance(
        ComplianceCheckRequest(vendor_id=payload.vendor_id, amount_usd=payload.amount_usd),
        session=session,
    )

    po = PurchaseOrder(
        po_number=_generate_po_number(payload.vendor_id, payload.amount_usd),
        vendor_id=payload.vendor_id,
        amount_usd=payload.amount_usd,
        requested_by=payload.requested_by,
        status="issued" if result.cleared else "pending_approval",
        compliance_note=result.reason,
    )
    session.add(po)
    session.commit()
    session.refresh(po)
    return po


@router.post("/{po_id}/approve", response_model=PurchaseOrder)
def approve_purchase_order(po_id: int, payload: PurchaseOrderApprove, session: Session = Depends(get_session)):
    from app.models import utcnow

    po = session.get(PurchaseOrder, po_id)
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    if po.status != "pending_approval":
        raise HTTPException(status_code=409, detail=f"PO is '{po.status}', not awaiting approval.")

    po.status = "issued"
    po.approved_by = payload.approved_by
    po.approved_at = utcnow()
    session.add(po)
    session.commit()
    session.refresh(po)
    return po


@router.get("/{po_id}", response_model=PurchaseOrder)
def get_purchase_order(po_id: int, session: Session = Depends(get_session)):
    po = session.get(PurchaseOrder, po_id)
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    return po
