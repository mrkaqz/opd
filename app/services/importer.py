"""One-time import of Patient List.xlsm → SQLite (via uploaded file bytes)."""
import io
from datetime import datetime

import openpyxl
from sqlalchemy.orm import Session

from app.models import OpdVisit, OpdPatient, OpdPhone, OpdOwner
from app.schemas import ImportResult

# Column indices (0-based) in the "List" sheet
COL_OPD    = 0   # A – OPD#
COL_OWNER  = 1   # B – Owner name
COL_OWNER2 = 2   # C – Owner name 2
COL_PET    = 3   # D – Pet name
COL_TYPE   = 4   # E – Pet type
COL_PHONE  = 5   # F – Phone


def _str(val) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


def run_import(db: Session, file_bytes: bytes) -> ImportResult:
    wb = openpyxl.load_workbook(
        io.BytesIO(file_bytes), read_only=True, keep_vba=True
    )
    ws = wb["List"]

    visits_created = 0
    patients_created = 0
    skipped = 0
    errors: list[str] = []

    # Track what's already in DB
    existing_visits: set[int] = {v for (v,) in db.query(OpdVisit.opd_number).all()}
    existing_phones: dict[int, set[str]] = {}
    for opd_num, phone in db.query(OpdPhone.opd_number, OpdPhone.phone).all():
        existing_phones.setdefault(opd_num, set()).add(phone)
    existing_owners: dict[int, set[str]] = {}
    for opd_num, name in db.query(OpdOwner.opd_number, OpdOwner.owner_name).all():
        existing_owners.setdefault(opd_num, set()).add(name)

    # Track what we've added in this batch
    seen_visits: set[int] = set()
    batch_phones: dict[int, set[str]] = {}
    batch_owners: dict[int, set[str]] = {}

    for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        try:
            raw_opd = row[COL_OPD]
            if raw_opd is None:
                skipped += 1
                continue

            try:
                opd_num = int(float(str(raw_opd).strip()))
            except ValueError:
                skipped += 1
                continue

            pet_name = _str(row[COL_PET])
            if not pet_name:
                skipped += 1
                continue

            phone      = _str(row[COL_PHONE])
            owner_name  = _str(row[COL_OWNER])
            owner_name2 = _str(row[COL_OWNER2])

            # Create visit row if new
            if opd_num not in existing_visits and opd_num not in seen_visits:
                db.add(OpdVisit(
                    opd_number=opd_num,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                ))
                seen_visits.add(opd_num)
                batch_phones[opd_num] = set()
                batch_owners[opd_num] = set()
                visits_created += 1

            # Add phone (deduplicated per OPD)
            if phone:
                db_phones  = existing_phones.get(opd_num, set())
                new_phones = batch_phones.get(opd_num, set())
                if phone not in db_phones and phone not in new_phones:
                    db.add(OpdPhone(opd_number=opd_num, phone=phone,
                                    created_at=datetime.utcnow()))
                    batch_phones.setdefault(opd_num, set()).add(phone)

            # Add owner names (deduplicated per OPD)
            for name in filter(None, [owner_name, owner_name2]):
                db_owners  = existing_owners.get(opd_num, set())
                new_owners = batch_owners.get(opd_num, set())
                if name not in db_owners and name not in new_owners:
                    db.add(OpdOwner(opd_number=opd_num, owner_name=name,
                                    created_at=datetime.utcnow()))
                    batch_owners.setdefault(opd_num, set()).add(name)

            db.add(OpdPatient(
                opd_number=opd_num,
                pet_name=pet_name,
                pet_type=_str(row[COL_TYPE]),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            ))
            patients_created += 1

            if patients_created % 500 == 0:
                db.flush()

        except Exception as exc:
            errors.append(f"Row {row_idx}: {exc}")
            skipped += 1

    db.commit()
    wb.close()

    return ImportResult(
        visits_created=visits_created,
        patients_created=patients_created,
        skipped_rows=skipped,
        errors=errors[:50],
    )
