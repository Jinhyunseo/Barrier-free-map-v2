from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import BACKEND_DIR, settings
from app.core.database import get_db
from app.models.models import (
    EquipmentStatus,
    Facility,
    FacilityEquipment,
    FacilityStatus,
    Report,
    User,
)
from app.schemas.report import ReportResponse
from app.services.report_ai_service import verify_report_image


router = APIRouter(prefix="/reports", tags=["Reports (사진 제보)"])

UPLOAD_DIR = BACKEND_DIR / "static" / "uploads" / "reports"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_REPORT_TYPES = {"STAIRS", "ELEVATOR_OUT", "ESCALATOR_OUT", "ROAD_BLOCK", "OTHER"}
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}


def _normalize(value: str | None) -> str:
    return re.sub(r"\s+", "", (value or "").lower())


async def _resolve_facility(db: AsyncSession, location_text: str | None) -> Facility | None:
    target = _normalize(location_text)
    if not target:
        return None

    # 프로젝트 규모(성남시 정류장 약 1,300개)에서는 전체 이름 비교도 충분히 가볍고,
    # "판교역 1번 출구"처럼 부가 문구가 붙어도 가장 긴 시설명을 찾을 수 있습니다.
    rows = (
        await db.execute(
            select(Facility).order_by(desc(Facility.standard_name))
        )
    ).scalars().all()

    candidates: list[Facility] = []
    for row in rows:
        names = [row.standard_name, row.station_name, row.external_code]
        if any(_normalize(name) and _normalize(name) in target for name in names):
            candidates.append(row)

    if not candidates:
        return None

    candidates.sort(key=lambda x: len(_normalize(x.standard_name)), reverse=True)
    return candidates[0]


async def _resolve_equipment(
    db: AsyncSession,
    facility_id: int | None,
    report_type: str,
    location_text: str | None,
) -> FacilityEquipment | None:
    if facility_id is None:
        return None

    equipment_type = None
    if report_type == "ELEVATOR_OUT":
        equipment_type = "ELEVATOR"
    elif report_type == "ESCALATOR_OUT":
        equipment_type = "ESCALATOR"

    if equipment_type is None:
        return None

    rows = (
        await db.execute(
            select(FacilityEquipment).where(
                FacilityEquipment.facility_id == facility_id,
                FacilityEquipment.equipment_type == equipment_type,
            )
        )
    ).scalars().all()

    if len(rows) == 1:
        return rows[0]

    text = location_text or ""
    exit_match = re.search(r"(\d+)\s*번\s*출(?:구|입구)", text)
    if exit_match:
        exit_no = exit_match.group(1)
        matched = [row for row in rows if row.exit_no and exit_no in row.exit_no]
        if len(matched) == 1:
            return matched[0]

    return None


def _extension_for(content_type: str, original_name: str | None) -> str:
    mapping = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/heic": ".heic",
        "image/heif": ".heif",
    }
    return mapping.get(content_type) or Path(original_name or "").suffix.lower() or ".img"


def _decide_report_status(report_type: str, ai_result) -> str:
    """AI 결과가 실제 장애 제보 자동 승인 조건을 충족하는지 결정합니다."""
    issue_statuses = {"BROKEN", "MAINTENANCE", "BLOCKED"}
    expected_equipment = {
        "ELEVATOR_OUT": "ELEVATOR",
        "ESCALATOR_OUT": "ESCALATOR",
    }.get(report_type)
    equipment_matches = (
        expected_equipment is None
        or ai_result.detected_equipment_type in {expected_equipment, "UNKNOWN"}
    )

    if (
        ai_result.verification == "ACCEPTED"
        and ai_result.confidence_score >= settings.REPORT_AI_ACCEPT_THRESHOLD
        and ai_result.detected_status in issue_statuses
        and equipment_matches
    ):
        return "ACCEPTED"
    if ai_result.verification == "REJECTED":
        return "REJECTED"
    return "PENDING_REVIEW"


@router.post("", response_model=ReportResponse, status_code=201)
async def create_report(
    report_type: str = Form(..., description="STAIRS, ELEVATOR_OUT, ESCALATOR_OUT, ROAD_BLOCK, OTHER"),
    title: str = Form(..., min_length=1, max_length=255),
    description: str | None = Form(None),
    location_text: str | None = Form(None, description="장소/위치 텍스트. 비우면 title을 사용합니다."),
    user_id: int = Form(settings.DEFAULT_REPORT_USER_ID),
    facility_id: int | None = Form(None),
    equipment_id: int | None = Form(None),
    captured_latitude: float | None = Form(None),
    captured_longitude: float | None = Form(None),
    image: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
):
    report_type = report_type.strip().upper()
    if report_type not in ALLOWED_REPORT_TYPES:
        raise HTTPException(status_code=422, detail=f"지원하지 않는 report_type입니다: {report_type}")

    if captured_latitude is not None and not -90 <= captured_latitude <= 90:
        raise HTTPException(status_code=422, detail="captured_latitude는 -90~90 범위여야 합니다.")
    if captured_longitude is not None and not -180 <= captured_longitude <= 180:
        raise HTTPException(status_code=422, detail="captured_longitude는 -180~180 범위여야 합니다.")

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="사용자 정보를 찾을 수 없습니다. 먼저 사용자 seed 또는 로그인 연동이 필요합니다.")

    resolved_location = (location_text or title).strip()

    facility = await db.get(Facility, facility_id) if facility_id else None
    if facility_id and facility is None:
        raise HTTPException(status_code=404, detail="facility_id에 해당하는 시설이 없습니다.")
    if facility is None:
        facility = await _resolve_facility(db, resolved_location)

    equipment = await db.get(FacilityEquipment, equipment_id) if equipment_id else None
    if equipment_id and equipment is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"equipment_id={equipment_id}에 해당하는 장비가 없습니다. "
                "equipment_id는 facility_id와 다른 값입니다. "
                "모르면 비워두면 위치/제보유형으로 자동 탐색하고, "
                "필요하면 GET /facilities/{facility_id}/equipment에서 확인하세요."
            ),
        )
    if equipment and facility and equipment.facility_id != facility.facility_id:
        raise HTTPException(status_code=422, detail="선택한 장비가 해당 시설에 속하지 않습니다.")
    if equipment is None:
        equipment = await _resolve_equipment(
            db,
            facility.facility_id if facility else None,
            report_type,
            resolved_location,
        )

    image_bytes: bytes | None = None
    image_url: str | None = None
    target_path: Path | None = None
    ai_verification = "NOT_RUN"
    ai_confidence_score = None
    detected_status = None
    reason = None
    report_status = "RECEIVED"

    if image is not None and image.filename:
        content_type = (image.content_type or "").lower()
        if content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=415, detail="jpg, png, webp, heic 이미지 파일만 업로드할 수 있습니다.")

        image_bytes = await image.read()
        max_bytes = settings.MAX_REPORT_IMAGE_MB * 1024 * 1024
        if len(image_bytes) > max_bytes:
            raise HTTPException(status_code=413, detail=f"이미지는 {settings.MAX_REPORT_IMAGE_MB}MB 이하만 업로드할 수 있습니다.")
        if not image_bytes:
            raise HTTPException(status_code=400, detail="빈 이미지 파일입니다.")

        filename = f"{uuid4().hex}{_extension_for(content_type, image.filename)}"
        target_path = UPLOAD_DIR / filename
        target_path.write_bytes(image_bytes)
        image_url = f"/static/uploads/reports/{filename}"

        ai_result = await verify_report_image(
            image_bytes=image_bytes,
            mime_type=content_type,
            report_type=report_type,
            title=title,
            description=description,
            location_text=resolved_location,
        )
        if ai_result is None:
            ai_verification = "NOT_RUN"
            report_status = "PENDING_REVIEW"
            reason = "AI 검수를 실행하지 못해 수동 검수 대기 상태로 저장했습니다."
        else:
            ai_verification = ai_result.verification
            ai_confidence_score = ai_result.confidence_score
            detected_status = ai_result.detected_status
            reason = ai_result.reason

            # 고장/통제 제보는 관련 시설 사진이라는 이유만으로 자동 승인하지 않습니다.
            report_status = _decide_report_status(report_type, ai_result)
    else:
        report_status = "PENDING_REVIEW"
        reason = "사진이 첨부되지 않아 수동 검수 대기 상태로 저장했습니다."

    report = Report(
        user_id=user_id,
        facility_id=facility.facility_id if facility else None,
        equipment_id=equipment.equipment_id if equipment else None,
        report_type=report_type,
        title=title.strip(),
        description=description.strip() if description else None,
        location_text=resolved_location,
        captured_latitude=captured_latitude,
        captured_longitude=captured_longitude,
        image_url=image_url,
        report_status=report_status,
        ai_verification=ai_verification,
        ai_confidence_score=ai_confidence_score,
        detected_status=detected_status,
        reason=reason,
    )
    try:
        db.add(report)
        await db.flush()

        # AI가 충분한 신뢰도로 실제 장애 상태를 승인한 경우에만 서비스 상태 이력을 갱신합니다.
        if report_status == "ACCEPTED" and detected_status in {"BROKEN", "MAINTENANCE", "BLOCKED"}:
            status_detail = f"AI 승인 사용자 제보 #{report.report_id}: {reason or title}"
            if equipment is not None:
                db.add(
                    EquipmentStatus(
                        equipment_id=equipment.equipment_id,
                        status_code=detected_status,
                        source="USER_REPORT_AI",
                        detail=status_detail,
                    )
                )
            elif facility is not None and report_type not in {"ELEVATOR_OUT", "ESCALATOR_OUT"}:
                # 장비 고장 제보에서 정확한 장비를 특정하지 못했다고 역 전체를 고장으로 표시하면 안 됩니다.
                db.add(
                    FacilityStatus(
                        facility_id=facility.facility_id,
                        status_code=detected_status,
                        source="USER_REPORT_AI",
                        detail=status_detail,
                    )
                )

        await db.commit()
        await db.refresh(report)
        return ReportResponse.model_validate(report)
    except Exception:
        await db.rollback()
        # DB 저장 실패 시 VM 디스크에 고아 이미지가 남지 않도록 제거합니다.
        if image_url and target_path is not None and target_path.exists():
            target_path.unlink(missing_ok=True)
        raise


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(report_id: int, db: AsyncSession = Depends(get_db)):
    report = await db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="제보 내역을 찾을 수 없습니다.")
    return ReportResponse.model_validate(report)


@router.get("", response_model=list[ReportResponse])
async def list_reports(
    user_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Report)
    if user_id is not None:
        stmt = stmt.where(Report.user_id == user_id)
    stmt = stmt.order_by(desc(Report.created_at), desc(Report.report_id)).limit(limit)
    reports = (await db.execute(stmt)).scalars().all()
    return [ReportResponse.model_validate(report) for report in reports]
