from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import Vendor
from app.schemas import VendorCreate

router = APIRouter(prefix="/vendors", tags=["vendors"])


@router.get("", response_model=list[Vendor])
def list_vendors(
    category: Optional[str] = None,
    min_rating: float = 0.0,
    session: Session = Depends(get_session),
):
    """This is what the vendor_sourcing agent's search_vendors tool calls."""
    query = select(Vendor).where(Vendor.rating >= min_rating, Vendor.status == "active")
    if category:
        query = query.where(Vendor.category == category)
    return session.exec(query).all()


@router.post("", response_model=Vendor, status_code=201)
def create_vendor(payload: VendorCreate, session: Session = Depends(get_session)):
    vendor = Vendor(**payload.model_dump())
    session.add(vendor)
    session.commit()
    session.refresh(vendor)
    return vendor


@router.get("/{vendor_id}", response_model=Vendor)
def get_vendor(vendor_id: int, session: Session = Depends(get_session)):
    vendor = session.get(Vendor, vendor_id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return vendor
