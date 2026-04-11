from datetime import datetime
from sqlalchemy import Integer, String, DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class OpdVisit(Base):
    __tablename__ = "opd_visits"

    opd_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    onedrive_item_id: Mapped[str | None] = mapped_column(String, nullable=True)
    web_url: Mapped[str | None] = mapped_column(String, nullable=True)
    file_name: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    patients: Mapped[list["OpdPatient"]] = relationship(
        "OpdPatient", back_populates="visit", cascade="all, delete-orphan"
    )
    phones: Mapped[list["OpdPhone"]] = relationship(
        "OpdPhone", back_populates="visit", cascade="all, delete-orphan"
    )
    owners: Mapped[list["OpdOwner"]] = relationship(
        "OpdOwner", back_populates="visit", cascade="all, delete-orphan"
    )


class OpdPatient(Base):
    __tablename__ = "opd_patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    opd_number: Mapped[int] = mapped_column(
        Integer, ForeignKey("opd_visits.opd_number", ondelete="CASCADE"), nullable=False
    )
    pet_name: Mapped[str] = mapped_column(String, nullable=False)
    pet_type: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    visit: Mapped["OpdVisit"] = relationship("OpdVisit", back_populates="patients")

    __table_args__ = (
        Index("ix_opd_patients_opd_number", "opd_number"),
    )


class OpdPhone(Base):
    __tablename__ = "opd_phones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    opd_number: Mapped[int] = mapped_column(
        Integer, ForeignKey("opd_visits.opd_number", ondelete="CASCADE"), nullable=False
    )
    phone: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    visit: Mapped["OpdVisit"] = relationship("OpdVisit", back_populates="phones")

    __table_args__ = (
        Index("ix_opd_phones_opd_number", "opd_number"),
        Index("ix_opd_phones_phone", "phone"),
    )


class OpdOwner(Base):
    __tablename__ = "opd_owners"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    opd_number: Mapped[int] = mapped_column(
        Integer, ForeignKey("opd_visits.opd_number", ondelete="CASCADE"), nullable=False
    )
    owner_name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    visit: Mapped["OpdVisit"] = relationship("OpdVisit", back_populates="owners")

    __table_args__ = (
        Index("ix_opd_owners_opd_number", "opd_number"),
        Index("ix_opd_owners_owner_name", "owner_name"),
    )


class AuthToken(Base):
    __tablename__ = "auth_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String, nullable=False)
    token_cache: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class AppConfig(Base):
    __tablename__ = "app_config"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
