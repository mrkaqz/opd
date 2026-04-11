from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from app.database import init_db
from app.routers import visits, patients, phones, owners, auth, onedrive
from app.routers.visits import admin_router

app = FastAPI(title="Clinic OPD", version="1.0.0")

# ── Init DB on startup ────────────────────────────────────────────────────────
@app.on_event("startup")
def on_startup():
    init_db()


# ── API routers ───────────────────────────────────────────────────────────────
app.include_router(visits.router)
app.include_router(patients.router)
app.include_router(phones.router)
app.include_router(owners.router)
app.include_router(auth.router)
app.include_router(onedrive.router)
app.include_router(admin_router)


# ── Static frontend ───────────────────────────────────────────────────────────
STATIC_DIR = Path(__file__).parent / "static"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/{full_path:path}", include_in_schema=False)
def spa_fallback(full_path: str):
    """Serve index.html for all non-API routes (SPA)."""
    return FileResponse(str(STATIC_DIR / "index.html"))
