from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import OpdVisit, OpdPatient
from app.schemas import PatientCreate, PatientUpdate, PatientOut

router = APIRouter(
    prefix="/api/visits/{opd_number}/patients",
    tags=["patients"],
)


def _get_visit_or_404(opd_number: int, db: Session) -> OpdVisit:
    visit = db.get(OpdVisit, opd_number)
    if not visit:
        raise HTTPException(status_code=404, detail="OPD not found")
    return visit


@router.post("", response_model=PatientOut, status_code=201)
def add_patient(
    opd_number: int,
    body: PatientCreate,
    db: Session = Depends(get_db),
):
    _get_visit_or_404(opd_number, db)
    patient = OpdPatient(opd_number=opd_number, **body.model_dump())
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


@router.put("/{patient_id}", response_model=PatientOut)
def update_patient(
    opd_number: int,
    patient_id: int,
    body: PatientUpdate,
    db: Session = Depends(get_db),
):
    _get_visit_or_404(opd_number, db)
    patient = db.get(OpdPatient, patient_id)
    if not patient or patient.opd_number != opd_number:
        raise HTTPException(status_code=404, detail="Patient not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(patient, field, value)

    db.commit()
    db.refresh(patient)
    return patient


@router.delete("/{patient_id}", status_code=204)
def delete_patient(
    opd_number: int,
    patient_id: int,
    db: Session = Depends(get_db),
):
    _get_visit_or_404(opd_number, db)
    patient = db.get(OpdPatient, patient_id)
    if not patient or patient.opd_number != opd_number:
        raise HTTPException(status_code=404, detail="Patient not found")
    db.delete(patient)
    db.commit()
