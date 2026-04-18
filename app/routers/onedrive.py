from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import OpdVisit
from app.schemas import FileInfo, FolderItem
from app.services import onedrive as od

router = APIRouter(prefix="/api/onedrive", tags=["onedrive"])


@router.get("/debug-folder")
def debug_folder(db: Session = Depends(get_db)):
    """List first 20 files in the configured folder for debugging."""
    import httpx
    from app.services.onedrive import _get_token, _headers, get_config, GRAPH_BASE
    token = _get_token(db)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    folder_id = get_config(db, "onedrive_folder_id")
    if not folder_id:
        raise HTTPException(status_code=400, detail="No folder configured")
    with httpx.Client() as client:
        resp = client.get(
            f"{GRAPH_BASE}/me/drive/items/{folder_id}/children",
            headers=_headers(token),
            params={"$select": "id,name,size,file", "$top": "20"},
        )
        resp.raise_for_status()
    items = resp.json().get("value", [])
    return {
        "folder_id": folder_id,
        "files": [{"name": i["name"], "is_file": "file" in i} for i in items],
        "lookup_would_use": "GET /me/drive/items/{folder_id}:/{opd_number}.pdf",
    }


@router.get("/folders", response_model=list[FolderItem])
def list_folders(db: Session = Depends(get_db)):
    try:
        folders = od.list_root_folders(db)
        return [FolderItem(**f) for f in folders]
    except RuntimeError as exc:
        raise HTTPException(status_code=401, detail=str(exc))


@router.get("/folders/{item_id}", response_model=list[FolderItem])
def list_subfolders(item_id: str, db: Session = Depends(get_db)):
    try:
        folders = od.list_subfolders(db, item_id)
        return [FolderItem(**f) for f in folders]
    except RuntimeError as exc:
        raise HTTPException(status_code=401, detail=str(exc))


@router.post("/folder")
def set_folder(item_id: str, name: str = "", db: Session = Depends(get_db)):
    """Save the chosen OneDrive folder ID and name to app_config."""
    od.set_config(db, "onedrive_folder_id", item_id)
    od.set_config(db, "onedrive_folder_name", name)
    return {"status": "ok", "folder_id": item_id, "folder_name": name}


@router.get("/folder")
def get_folder(db: Session = Depends(get_db)):
    folder_id   = od.get_config(db, "onedrive_folder_id")
    folder_name = od.get_config(db, "onedrive_folder_name") or folder_id or ""
    return {"folder_id": folder_id, "folder_name": folder_name}


@router.get("/file/{opd_number}", response_model=FileInfo)
def get_opd_file(opd_number: int, db: Session = Depends(get_db)):
    """
    Look up {opd_number}.pdf in the configured OneDrive folder.
    Caches result in opd_visits row.
    """
    visit = db.get(OpdVisit, opd_number)
    if not visit:
        raise HTTPException(status_code=404, detail="OPD not found")

    # Return cached value if present
    if visit.web_url and visit.onedrive_item_id:
        return FileInfo(
            item_id=visit.onedrive_item_id,
            name=visit.file_name or f"{opd_number}.pdf",
            web_url=visit.web_url,
            found=True,
        )

    # Query OneDrive
    try:
        info = od.find_opd_file(db, opd_number)
    except RuntimeError as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    if not info:
        return FileInfo(item_id="", name="", web_url="", found=False)

    # Cache in DB
    visit.onedrive_item_id = info["item_id"]
    visit.web_url = info["web_url"]
    visit.file_name = info["name"]
    db.commit()

    return FileInfo(
        item_id=info["item_id"],
        name=info["name"],
        web_url=info["web_url"],
        found=True,
    )


@router.delete("/file/{opd_number}", status_code=204)
def clear_cached_file(opd_number: int, db: Session = Depends(get_db)):
    """Clear cached OneDrive file reference (force re-lookup)."""
    visit = db.get(OpdVisit, opd_number)
    if not visit:
        raise HTTPException(status_code=404, detail="OPD not found")
    visit.onedrive_item_id = None
    visit.web_url = None
    visit.file_name = None
    db.commit()
