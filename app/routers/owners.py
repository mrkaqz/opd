from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import OpdVisit, OpdOwner
from app.schemas import OwnerCreate, OwnerOut

router = APIRouter(
    prefix="/api/visits/{opd_number}/owners",
    tags=["owners"],
)


def _get_visit_or_404(opd_number: int, db: Session) -> OpdVisit:
    visit = db.get(OpdVisit, opd_number)
    if not visit:
        raise HTTPException(status_code=404, detail="OPD not found")
    return visit


@router.post("", response_model=OwnerOut, status_code=201)
def add_owner(opd_number: int, body: OwnerCreate, db: Session = Depends(get_db)):
    _get_visit_or_404(opd_number, db)
    owner = OpdOwner(opd_number=opd_number, owner_name=body.owner_name)
    db.add(owner)
    db.commit()
    db.refresh(owner)
    return owner


@router.delete("/{owner_id}", status_code=204)
def delete_owner(opd_number: int, owner_id: int, db: Session = Depends(get_db)):
    _get_visit_or_404(opd_number, db)
    owner = db.get(OpdOwner, owner_id)
    if not owner or owner.opd_number != opd_number:
        raise HTTPException(status_code=404, detail="Owner not found")
    db.delete(owner)
    db.commit()
