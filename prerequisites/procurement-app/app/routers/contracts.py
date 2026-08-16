from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import Contract, Vendor
from app.schemas import ContractCreate

router = APIRouter(tags=["contracts"])


@router.post("/contracts", response_model=Contract, status_code=201)
def create_contract(payload: ContractCreate, session: Session = Depends(get_session)):
    if not session.get(Vendor, payload.vendor_id):
        raise HTTPException(status_code=404, detail="Vendor not found")
    contract = Contract(**payload.model_dump())
    session.add(contract)
    session.commit()
    session.refresh(contract)
    return contract


@router.get("/vendors/{vendor_id}/contract", response_model=Contract)
def get_vendor_contract(vendor_id: int, session: Session = Depends(get_session)):
    """This is what the contract_review agent's get_vendor_contract_terms
    tool calls -- returns the active contract for a vendor."""
    contract = session.exec(
        select(Contract).where(Contract.vendor_id == vendor_id, Contract.status == "active")
    ).first()
    if not contract:
        raise HTTPException(status_code=404, detail="No active contract for this vendor")
    return contract
