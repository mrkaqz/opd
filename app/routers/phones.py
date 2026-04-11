from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import OpdVisit, OpdPhone
from app.schemas import PhoneCreate, PhoneOut

router = APIRouter(
    prefix="/api/visits/{opd_number}/phones",
    tags=["phones"],
)


def _get_visit_or_404(opd_number: int, db: Session) -> OpdVisit:
    visit = db.get(OpdVisit, opd_number)
    if not visit:
        raise HTTPException(status_code=404, detail="OPD not found")
    return visit


@router.post("", response_model=PhoneOut, status_code=201)
def add_phone(opd_number: int, body: PhoneCreate, db: Session = Depends(get_db)):
    _get_visit_or_404(opd_number, db)
    phone = OpdPhone(opd_number=opd_number, phone=body.phone)
    db.add(phone)
    db.commit()
    db.refresh(phone)
    return phone


@router.delete("/{phone_id}", status_code=204)
def delete_phone(opd_number: int, phone_id: int, db: Session = Depends(get_db)):
    _get_visit_or_404(opd_number, db)
    phone = db.get(OpdPhone, phone_id)
    if not phone or phone.opd_number != opd_number:
        raise HTTPException(status_code=404, detail="Phone not found")
    db.delete(phone)
    db.commit()
