from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import OpdVisit
from app.schemas import FileInfo, FolderItem
from app.services import onedrive as od

router = APIRouter(prefix="/api/onedrive", tags=["onedrive"])


@router.get("/folders", response_model=list[FolderItem])
def list_folders(db: Session = Depends(get_db)):
    try:
        folders = od.list_root_folders(db)
        return [FolderItem(**f) for f in folders]
    except RuntimeError as exc:
        raise HTTPException(status_code=401, detail=str(exc))


@router.post("/folder")
def set_folder(item_id: str, db: Session = Depends(get_db)):
    """Save the chosen OneDrive folder ID to app_config."""
    od.set_config(db, "onedrive_folder_id", item_id)
    return {"status": "ok", "folder_id": item_id}


@router.get("/folder")
def get_folder(db: Session = Depends(get_db)):
    folder_id = od.get_config(db, "onedrive_folder_id")
    return {"folder_id": folder_id}


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
