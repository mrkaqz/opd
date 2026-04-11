from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from pathlib import Path
import os

_default_db = str(Path(__file__).parent.parent / "data" / "clinic.db")
DB_PATH = os.environ.get("DB_PATH", _default_db)
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app.models import OpdVisit, OpdPatient, OpdPhone, OpdOwner, AuthToken, AppConfig  # noqa
    _migrate(engine)
    Base.metadata.create_all(bind=engine)


def _migrate(eng):
    """Apply incremental SQLite schema migrations."""
    with eng.connect() as conn:

        # v1: move phone from opd_patients → opd_visits (legacy column, kept as dead weight)
        visit_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(opd_visits)"))}
        if "phone" not in visit_cols:
            conn.execute(text("ALTER TABLE opd_visits ADD COLUMN phone TEXT"))
            conn.execute(text("""
                UPDATE opd_visits
                SET phone = (
                    SELECT phone FROM opd_patients
                    WHERE opd_patients.opd_number = opd_visits.opd_number
                    AND phone IS NOT NULL LIMIT 1
                )
            """))
            conn.commit()

        tables = {row[0] for row in conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        )}

        # v2: opd_phones table — one row per phone per OPD
        if "opd_phones" not in tables:
            conn.execute(text("""
                CREATE TABLE opd_phones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    opd_number INTEGER NOT NULL
                        REFERENCES opd_visits(opd_number) ON DELETE CASCADE,
                    phone TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.execute(text(
                "CREATE INDEX ix_opd_phones_opd_number ON opd_phones (opd_number)"
            ))
            conn.execute(text(
                "CREATE INDEX ix_opd_phones_phone ON opd_phones (phone)"
            ))
            conn.execute(text("""
                INSERT INTO opd_phones (opd_number, phone, created_at)
                SELECT opd_number, phone, created_at
                FROM opd_visits
                WHERE phone IS NOT NULL AND phone != ''
            """))
            conn.commit()

        # v3: opd_owners table — one row per owner name per OPD
        if "opd_owners" not in tables:
            conn.execute(text("""
                CREATE TABLE opd_owners (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    opd_number INTEGER NOT NULL
                        REFERENCES opd_visits(opd_number) ON DELETE CASCADE,
                    owner_name TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.execute(text(
                "CREATE INDEX ix_opd_owners_opd_number ON opd_owners (opd_number)"
            ))
            conn.execute(text(
                "CREATE INDEX ix_opd_owners_owner_name ON opd_owners (owner_name)"
            ))
            # Migrate owner_name (deduplicated per OPD)
            conn.execute(text("""
                INSERT INTO opd_owners (opd_number, owner_name, created_at)
                SELECT DISTINCT opd_number, owner_name, CURRENT_TIMESTAMP
                FROM opd_patients
                WHERE owner_name IS NOT NULL AND owner_name != ''
            """))
            # Migrate owner_name_2 (skip if already exists for that OPD)
            conn.execute(text("""
                INSERT INTO opd_owners (opd_number, owner_name, created_at)
                SELECT DISTINCT p.opd_number, p.owner_name_2, CURRENT_TIMESTAMP
                FROM opd_patients p
                WHERE p.owner_name_2 IS NOT NULL AND p.owner_name_2 != ''
                  AND NOT EXISTS (
                      SELECT 1 FROM opd_owners o
                      WHERE o.opd_number = p.opd_number
                        AND o.owner_name = p.owner_name_2
                  )
            """))
            conn.commit()
