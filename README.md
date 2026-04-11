# Clinic OPD

A veterinary clinic OPD (Outpatient Department) web management system built with FastAPI, SQLite, and Bootstrap 5.

![Docker](https://img.shields.io/badge/docker-ghcr.io%2Fmrkaqz%2Fopd-blue)
![Python](https://img.shields.io/badge/python-3.12-blue)
![License](https://img.shields.io/github/license/mrkaqz/opd)

## Features

- **OPD Visit Management** — create, search, paginate, and sort visits by any column
- **Multiple Phone Numbers** — add/remove multiple contact numbers per OPD
- **Multiple Owner Names** — add/remove multiple owner names per OPD
- **Patient Records** — track pets (name, type) linked to each OPD visit
- **Excel Import** — bulk import patient data from `.xlsm` / `.xlsx` files
- **OneDrive Integration** — link and preview patient files stored in OneDrive (requires Azure App Client ID)
- **Sortable Table** — click any column header to sort ascending/descending
- **Responsive UI** — Bootstrap 5 single-page app, works on desktop and tablet

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI + Uvicorn |
| Database | SQLite via SQLAlchemy ORM |
| Frontend | Bootstrap 5 (SPA, no framework) |
| Auth | MSAL (Microsoft Authentication Library) |
| Import | openpyxl |
| Container | Docker (amd64 + arm64) |

## Quick Start

### Option A — Docker (recommended)

```bash
# Pull latest image
docker pull ghcr.io/mrkaqz/opd:latest

# Run with persistent database
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  --name clinic-opd \
  ghcr.io/mrkaqz/opd:latest
```

Open http://localhost:8000

### Option B — Docker Compose

```bash
# Copy and edit environment file
cp .env.example .env

# Start
docker compose up -d
```

### Option C — Local Development

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DB_PATH` | Path to SQLite database file | `/app/data/clinic.db` |
| `AZURE_CLIENT_ID` | Azure App Registration Client ID (for OneDrive) | *(empty)* |

## OneDrive Integration (Optional)

To enable patient file linking via OneDrive:

1. Register an app at [portal.azure.com](https://portal.azure.com) → Microsoft Entra ID → App registrations
2. Set **Redirect URI** to `https://login.microsoftonline.com/common/oauth2/nativeclient`
3. Add delegated permission: `Files.Read.All`
4. Copy the **Application (client) ID**
5. Set it in the app's **Settings** page or via the `AZURE_CLIENT_ID` environment variable

## Releasing a New Version

Tag a commit to trigger the Docker build & push workflow:

```bash
git tag v1.0.0
git push origin v1.0.0
```

GitHub Actions will build multi-platform images (`amd64` + `arm64`) and push to:
- `ghcr.io/mrkaqz/opd:1.0.0`
- `ghcr.io/mrkaqz/opd:latest`

## Data

- The SQLite database is stored in `./data/clinic.db` (mounted as a volume in Docker)
- Patient files are not stored in this app — they are linked from OneDrive
- Import patient history via **Settings → Import Excel** in the UI

## License

MIT
