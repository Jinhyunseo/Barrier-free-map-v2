from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "user"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    nickname: Mapped[str] = mapped_column(String(100), nullable=False)
    # seed 사용자처럼 로그인 비밀번호가 없는 초기 데이터도 유지할 수 있도록 nullable=True로 둡니다.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    reports: Mapped[list["Report"]] = relationship(back_populates="user")


class Transportation(Base):
    __tablename__ = "transportation"
    __table_args__ = (
        UniqueConstraint("transport_type", "external_code", name="uq_transportation_type_external"),
    )

    transportation_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transport_type: Mapped[str] = mapped_column(String(30), nullable=False)  # BUS, SUBWAY
    route_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    external_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    operator_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    is_low_floor: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    start_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    end_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class Facility(Base):
    __tablename__ = "facility"
    __table_args__ = (
        UniqueConstraint("facility_type", "external_code", name="uq_facility_type_external"),
        Index("ix_facility_standard_name", "standard_name"),
    )

    facility_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    facility_type: Mapped[str] = mapped_column(String(30), nullable=False)  # STATION, BUS_STOP
    standard_name: Mapped[str] = mapped_column(String(200), nullable=False)
    station_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    line_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    external_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    equipment: Mapped[list["FacilityEquipment"]] = relationship(
        back_populates="facility",
        cascade="all, delete-orphan",
    )
    statuses: Mapped[list["FacilityStatus"]] = relationship(
        back_populates="facility",
        cascade="all, delete-orphan",
    )
    reports: Mapped[list["Report"]] = relationship(back_populates="facility")


class FacilityEquipment(Base):
    __tablename__ = "facility_equipment"
    __table_args__ = (
        # 같은 외부 장비번호가 다른 역사/운영기관에서 재사용될 가능성을 고려해 시설까지 묶어 중복을 막습니다.
        UniqueConstraint(
            "facility_id",
            "equipment_type",
            "external_equipment_no",
            name="uq_equipment_facility_type_external_no",
        ),
        Index("ix_equipment_facility_type", "facility_id", "equipment_type"),
    )

    equipment_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facility.facility_id", ondelete="CASCADE"), nullable=False)
    equipment_type: Mapped[str] = mapped_column(String(40), nullable=False)  # ELEVATOR, ESCALATOR, RAMP, ETC
    external_equipment_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    exit_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    detail_location: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    direction: Mapped[str | None] = mapped_column(String(50), nullable=True)
    from_floor: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_floor: Mapped[str | None] = mapped_column(String(30), nullable=True)
    capacity_persons: Mapped[int | None] = mapped_column(Integer, nullable=True)
    capacity_kg: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    facility: Mapped[Facility] = relationship(back_populates="equipment")
    statuses: Mapped[list["EquipmentStatus"]] = relationship(
        back_populates="equipment",
        cascade="all, delete-orphan",
    )
    reports: Mapped[list["Report"]] = relationship(back_populates="equipment")


class FacilityStatus(Base):
    __tablename__ = "facility_status"
    __table_args__ = (Index("ix_facility_status_facility_updated", "facility_id", "updated_at"),)

    facility_status_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facility.facility_id", ondelete="CASCADE"), nullable=False)
    status_code: Mapped[str] = mapped_column(String(30), nullable=False, default="UNKNOWN")
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="SEED")
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    facility: Mapped[Facility] = relationship(back_populates="statuses")


class EquipmentStatus(Base):
    __tablename__ = "equipment_status"
    __table_args__ = (Index("ix_equipment_status_equipment_updated", "equipment_id", "updated_at"),)

    equipment_status_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("facility_equipment.equipment_id", ondelete="CASCADE"), nullable=False)
    status_code: Mapped[str] = mapped_column(String(30), nullable=False, default="UNKNOWN")
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="SEED")
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    equipment: Mapped[FacilityEquipment] = relationship(back_populates="statuses")


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        Index("ix_reports_user_created", "user_id", "created_at"),
        Index("ix_reports_facility_created", "facility_id", "created_at"),
        Index("ix_reports_equipment_created", "equipment_id", "created_at"),
        Index("ix_reports_status_created", "report_status", "created_at"),
    )

    report_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.user_id"), nullable=False)
    facility_id: Mapped[int | None] = mapped_column(ForeignKey("facility.facility_id"), nullable=True)
    equipment_id: Mapped[int | None] = mapped_column(ForeignKey("facility_equipment.equipment_id"), nullable=True)

    report_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    captured_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    captured_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    report_status: Mapped[str] = mapped_column(String(30), nullable=False, default="RECEIVED")
    ai_verification: Mapped[str] = mapped_column(String(30), nullable=False, default="NOT_RUN")
    ai_confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    detected_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    user: Mapped[User] = relationship(back_populates="reports")
    facility: Mapped[Facility | None] = relationship(back_populates="reports")
    equipment: Mapped[FacilityEquipment | None] = relationship(back_populates="reports")
