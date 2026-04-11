from datetime import datetime
from pydantic import BaseModel, field_validator


# ── Patient schemas ──────────────────────────────────────────────────────────

class PatientBase(BaseModel):
    pet_name: str
    pet_type: str | None = None

    @field_validator("pet_name")
    @classmethod
    def pet_name_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("pet_name is required")
        return v.strip()


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    pet_name: str | None = None
    pet_type: str | None = None


class PatientOut(PatientBase):
    id: int
    opd_number: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Phone schemas ────────────────────────────────────────────────────────────

class PhoneCreate(BaseModel):
    phone: str

    @field_validator("phone")
    @classmethod
    def phone_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("phone is required")
        return v.strip()


class PhoneOut(BaseModel):
    id: int
    opd_number: int
    phone: str

    model_config = {"from_attributes": True}


# ── Owner schemas ────────────────────────────────────────────────────────────

class OwnerCreate(BaseModel):
    owner_name: str

    @field_validator("owner_name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("owner_name is required")
        return v.strip()


class OwnerOut(BaseModel):
    id: int
    opd_number: int
    owner_name: str

    model_config = {"from_attributes": True}


# ── Visit schemas ────────────────────────────────────────────────────────────

class VisitCreate(BaseModel):
    opd_number: int
    first_phone: str
    first_owner: str | None = None
    first_patient: PatientCreate

    @field_validator("first_phone")
    @classmethod
    def phone_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("first_phone is required")
        return v.strip()


class VisitOut(BaseModel):
    opd_number: int
    onedrive_item_id: str | None = None
    web_url: str | None = None
    file_name: str | None = None
    created_at: datetime
    updated_at: datetime
    patients: list[PatientOut] = []
    phones: list[PhoneOut] = []
    owners: list[OwnerOut] = []

    model_config = {"from_attributes": True}


class VisitSummary(BaseModel):
    """Compact row for the list view."""
    opd_number: int
    owners: str       # comma-joined owner names
    pets: str
    pet_types: str
    phones: str       # comma-joined phone numbers
    has_file: bool
    file_name: str | None = None
    web_url: str | None = None
    patient_count: int

    model_config = {"from_attributes": True}


class PaginatedVisits(BaseModel):
    total: int
    page: int
    limit: int
    items: list[VisitSummary]


# ── Phone search ─────────────────────────────────────────────────────────────

class PhoneSearchResult(BaseModel):
    opd_number: int
    phones: list[PhoneOut]
    owners: list[OwnerOut]
    patients: list[PatientOut]

    model_config = {"from_attributes": True}


# ── OneDrive / file ──────────────────────────────────────────────────────────

class FileInfo(BaseModel):
    item_id: str
    name: str
    web_url: str
    found: bool = True


class FolderItem(BaseModel):
    item_id: str
    name: str
    path: str


# ── Auth ─────────────────────────────────────────────────────────────────────

class DeviceCodeResponse(BaseModel):
    user_code: str
    verification_uri: str
    message: str


class AuthStatusResponse(BaseModel):
    authenticated: bool
    account: str | None = None


# ── Import ───────────────────────────────────────────────────────────────────

class ImportResult(BaseModel):
    visits_created: int
    patients_created: int
    skipped_rows: int
    errors: list[str]
