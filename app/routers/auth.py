import hashlib
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AppConfig
from app.schemas import DeviceCodeResponse, AuthStatusResponse
from app.services import onedrive as od


class ClientIdBody(BaseModel):
    client_id: str

router = APIRouter(prefix="/api/auth", tags=["auth"])

# ── PIN helpers ───────────────────────────────────────────────────────────────
_sessions: dict[str, float] = {}   # token → expiry (Unix timestamp)
_SESSION_TTL = 8 * 3600            # 8 hours


def _hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.encode()).hexdigest()


def _get_pin_hash(db: Session) -> str | None:
    row = db.get(AppConfig, "pin_hash")
    return row.value if row else None


def _pin_enabled(db: Session) -> bool:
    """PIN enforcement is ON by default when a hash exists; can be toggled off."""
    row = db.get(AppConfig, "pin_enabled")
    return (row.value != "0") if row else True


def _valid_session(token: str) -> bool:
    exp = _sessions.get(token)
    return exp is not None and time.time() < exp


def _new_session() -> str:
    token = str(uuid.uuid4())
    _sessions[token] = time.time() + _SESSION_TTL
    # Prune expired sessions opportunistically
    now = time.time()
    expired = [t for t, e in _sessions.items() if e < now]
    for t in expired:
        _sessions.pop(t, None)
    return token


class PinVerifyBody(BaseModel):
    pin: str

class PinSetBody(BaseModel):
    current_pin: str = ""
    new_pin: str = ""


# ── PIN endpoints ─────────────────────────────────────────────────────────────

@router.get("/pin-status")
def pin_status(token: str = Query(default=""), db: Session = Depends(get_db)):
    """Check if a PIN is configured/enabled and whether the session token is valid."""
    pin_hash = _get_pin_hash(db)
    enabled  = _pin_enabled(db)
    if not pin_hash or not enabled:
        return {"pin_set": bool(pin_hash), "pin_enabled": enabled, "authenticated": True}
    return {"pin_set": True, "pin_enabled": True, "authenticated": _valid_session(token)}


@router.post("/pin/verify")
def verify_pin(body: PinVerifyBody, db: Session = Depends(get_db)):
    """Validate PIN and return a session token."""
    pin_hash = _get_pin_hash(db)
    if not pin_hash:
        # No PIN set — always succeed
        return {"token": _new_session()}
    if _hash_pin(body.pin) != pin_hash:
        raise HTTPException(status_code=401, detail="Incorrect PIN")
    return {"token": _new_session()}


@router.post("/pin/set", status_code=200)
def set_pin(body: PinSetBody, db: Session = Depends(get_db)):
    """Set, change, or remove the PIN."""
    existing_hash = _get_pin_hash(db)

    # If PIN already set, require correct current PIN
    if existing_hash:
        if _hash_pin(body.current_pin) != existing_hash:
            raise HTTPException(status_code=401, detail="Current PIN is incorrect")

    new_pin = body.new_pin.strip()

    if new_pin == "":
        # Remove PIN
        row = db.get(AppConfig, "pin_hash")
        if row:
            db.delete(row)
            db.commit()
        return {"detail": "PIN removed"}

    if not new_pin.isdigit() or len(new_pin) != 4:
        raise HTTPException(status_code=422, detail="New PIN must be exactly 4 digits")

    row = db.get(AppConfig, "pin_hash")
    if row:
        row.value = _hash_pin(new_pin)
    else:
        db.add(AppConfig(key="pin_hash", value=_hash_pin(new_pin)))
    db.commit()
    return {"detail": "PIN updated"}


class PinEnabledBody(BaseModel):
    enabled: bool


@router.post("/pin/enabled", status_code=200)
def set_pin_enabled(body: PinEnabledBody, db: Session = Depends(get_db)):
    """Enable or disable PIN enforcement without removing the PIN hash."""
    row = db.get(AppConfig, "pin_enabled")
    val = "1" if body.enabled else "0"
    if row:
        row.value = val
    else:
        db.add(AppConfig(key="pin_enabled", value=val))
    db.commit()
    return {"detail": "PIN lock enabled" if body.enabled else "PIN lock disabled"}


@router.post("/start", response_model=DeviceCodeResponse)
def start_auth(db: Session = Depends(get_db)):
    if not od.get_client_id(db):
        raise HTTPException(
            status_code=503,
            detail="Azure Client ID is not configured. Please enter it in Settings.",
        )
    try:
        flow = od.start_device_code_flow(db)
        return DeviceCodeResponse(**flow)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/status", response_model=AuthStatusResponse)
def auth_status(db: Session = Depends(get_db)):
    # First check if we already have a valid token
    account = od.get_current_account(db)
    if account:
        return AuthStatusResponse(authenticated=True, account=account)

    # Try to poll for device-code completion
    result = od.poll_device_code(db)
    return AuthStatusResponse(
        authenticated=result["authenticated"],
        account=result.get("account"),
    )


@router.get("/me", response_model=AuthStatusResponse)
def me(db: Session = Depends(get_db)):
    account = od.get_current_account(db)
    return AuthStatusResponse(authenticated=bool(account), account=account)


@router.delete("/logout", status_code=204)
def logout(db: Session = Depends(get_db)):
    od.logout(db)


@router.get("/client-id")
def get_client_id(db: Session = Depends(get_db)):
    cid = od.get_client_id(db)
    return {"client_id": cid or ""}


@router.post("/client-id", status_code=204)
def set_client_id(body: ClientIdBody, db: Session = Depends(get_db)):
    od.set_config(db, "azure_client_id", body.client_id.strip())
