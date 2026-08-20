from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    report_id: int
    user_id: int
    facility_id: int | None
    equipment_id: int | None
    report_type: str
    title: str
    description: str | None
    location_text: str | None
    captured_latitude: float | None
    captured_longitude: float | None
    image_url: str | None
    report_status: str
    ai_verification: str
    ai_confidence_score: float | None
    detected_status: str | None
    reason: str | None
    created_at: datetime


class FacilitySearchItem(BaseModel):
    facility_id: int
    facility_type: str
    standard_name: str
    station_name: str | None = None
    line_name: str | None = None
    external_code: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class EquipmentItem(BaseModel):
    equipment_id: int
    equipment_type: str
    external_equipment_no: str | None = None
    exit_no: str | None = None
    detail_location: str | None = None
    direction: str | None = None
    latest_status: str | None = None
