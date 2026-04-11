from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import DeviceCodeResponse, AuthStatusResponse
from app.services import onedrive as od


class ClientIdBody(BaseModel):
    client_id: str

router = APIRouter(prefix="/api/auth", tags=["auth"])


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
