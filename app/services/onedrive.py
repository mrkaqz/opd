"""Microsoft Graph API helpers for OneDrive access."""
import json
import os
import threading
from typing import Optional

import httpx
import msal
from sqlalchemy.orm import Session

from app.models import AppConfig, AuthToken

# ── Azure App Registration ────────────────────────────────────────────────────
# Use a public client (no secret) with the Files.Read.All delegated scope.
# Register at https://portal.azure.com → App registrations → Mobile/Desktop app
# Redirect URI: https://login.microsoftonline.com/common/oauth2/nativeclient
_ENV_CLIENT_ID = os.environ.get("AZURE_CLIENT_ID", "")
AUTHORITY = "https://login.microsoftonline.com/common"
SCOPES = ["Files.Read.All"]  # offline_access is reserved — MSAL adds it automatically
GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def get_client_id(db: Session) -> str:
    """Return Client ID from DB config, falling back to env var."""
    row = db.get(AppConfig, "azure_client_id")
    return (row.value if row else None) or _ENV_CLIENT_ID


# Keep CLIENT_ID as a module-level alias for backwards compat (auth router check)
CLIENT_ID = _ENV_CLIENT_ID

# In-memory store for the device-code flow future (one at a time is fine)
_flow_lock = threading.Lock()
_active_flow: Optional[dict] = None
_msal_app: Optional[msal.PublicClientApplication] = None


def _get_msal_app(db: Session) -> msal.PublicClientApplication:
    global _msal_app
    cache = msal.SerializableTokenCache()

    token_row = db.query(AuthToken).first()
    if token_row:
        cache.deserialize(token_row.token_cache)

    app = msal.PublicClientApplication(
        get_client_id(db),
        authority=AUTHORITY,
        token_cache=cache,
    )
    _msal_app = app
    return app


def _persist_cache(app: msal.PublicClientApplication, db: Session):
    if not app.token_cache.has_state_changed:
        return
    serialized = app.token_cache.serialize()
    accounts = app.get_accounts()
    account_id = accounts[0]["home_account_id"] if accounts else "unknown"

    token_row = db.query(AuthToken).first()
    if token_row:
        token_row.token_cache = serialized
        token_row.account_id = account_id
    else:
        db.add(AuthToken(account_id=account_id, token_cache=serialized))
    db.commit()


def start_device_code_flow(db: Session) -> dict:
    global _active_flow
    app = _get_msal_app(db)
    with _flow_lock:
        flow = app.initiate_device_flow(scopes=SCOPES)
        if "user_code" not in flow:
            raise RuntimeError(f"Device flow failed: {flow.get('error_description')}")
        _active_flow = flow
    return {
        "user_code": flow["user_code"],
        "verification_uri": flow["verification_uri"],
        "message": flow["message"],
    }


def poll_device_code(db: Session) -> dict:
    global _active_flow
    with _flow_lock:
        if not _active_flow:
            return {"authenticated": False, "account": None}
        app = _get_msal_app(db)
        result = app.acquire_token_by_device_flow(_active_flow, exit_condition=lambda r: True)

    if "access_token" in result:
        _persist_cache(app, db)
        _active_flow = None
        accounts = app.get_accounts()
        return {
            "authenticated": True,
            "account": accounts[0]["username"] if accounts else None,
        }
    # Still pending or error
    error = result.get("error", "")
    if error == "authorization_pending":
        return {"authenticated": False, "account": None}
    return {"authenticated": False, "account": None, "error": error}


def get_current_account(db: Session) -> Optional[str]:
    app = _get_msal_app(db)
    accounts = app.get_accounts()
    return accounts[0]["username"] if accounts else None


def logout(db: Session):
    db.query(AuthToken).delete()
    db.commit()
    global _msal_app, _active_flow
    _msal_app = None
    _active_flow = None


def _get_token(db: Session) -> Optional[str]:
    app = _get_msal_app(db)
    accounts = app.get_accounts()
    if not accounts:
        return None
    result = app.acquire_token_silent(SCOPES, account=accounts[0])
    if result and "access_token" in result:
        _persist_cache(app, db)
        return result["access_token"]
    return None


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Config helpers ────────────────────────────────────────────────────────────

def get_config(db: Session, key: str) -> Optional[str]:
    row = db.get(AppConfig, key)
    return row.value if row else None


def set_config(db: Session, key: str, value: str):
    row = db.get(AppConfig, key)
    if row:
        row.value = value
    else:
        db.add(AppConfig(key=key, value=value))
    db.commit()


# ── Graph API calls ───────────────────────────────────────────────────────────

def _list_folders_url(token: str, url: str) -> list[dict]:
    with httpx.Client() as client:
        resp = client.get(
            url,
            headers=_headers(token),
            params={"$filter": "folder ne null", "$select": "id,name,parentReference"},
        )
        resp.raise_for_status()
        items = resp.json().get("value", [])
    return [
        {
            "item_id": i["id"],
            "name": i["name"],
            "path": i.get("parentReference", {}).get("path", "") + "/" + i["name"],
        }
        for i in items
    ]


def list_root_folders(db: Session) -> list[dict]:
    token = _get_token(db)
    if not token:
        raise RuntimeError("Not authenticated")
    return _list_folders_url(token, f"{GRAPH_BASE}/me/drive/root/children")


def list_subfolders(db: Session, item_id: str) -> list[dict]:
    token = _get_token(db)
    if not token:
        raise RuntimeError("Not authenticated")
    return _list_folders_url(token, f"{GRAPH_BASE}/me/drive/items/{item_id}/children")


def find_opd_file(db: Session, opd_number: int) -> Optional[dict]:
    """Look for {opd_number}.pdf in the configured folder using direct path lookup."""
    token = _get_token(db)
    if not token:
        return None

    folder_id = get_config(db, "onedrive_folder_id")
    if not folder_id:
        return None

    # Try filename variants in order: exact, 4-digit zero-padded, 5-digit zero-padded
    # Deduplicate while preserving order (e.g. OPD 1234 → "1234.pdf" appears in both exact and 4-digit)
    seen: set[str] = set()
    candidates: list[str] = []
    for name in [f"{opd_number}.pdf", f"{opd_number:04d}.pdf", f"{opd_number:05d}.pdf"]:
        if name not in seen:
            candidates.append(name)
            seen.add(name)

    # Direct path lookup — O(1) per candidate, works regardless of folder size
    with httpx.Client(timeout=15) as client:
        for filename in candidates:
            resp = client.get(
                f"{GRAPH_BASE}/me/drive/items/{folder_id}:/{filename}",
                headers=_headers(token),
                params={"$select": "id,name,webUrl"},
            )
            if resp.status_code == 200:
                item = resp.json()
                return {
                    "item_id": item["id"],
                    "name": item["name"],
                    "web_url": item["webUrl"],
                    "found": True,
                }
            elif resp.status_code == 404:
                continue  # Try next variant
            else:
                resp.raise_for_status()

    return None
