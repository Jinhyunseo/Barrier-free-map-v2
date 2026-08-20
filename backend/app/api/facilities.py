from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import EquipmentStatus, Facility, FacilityEquipment
from app.schemas.report import EquipmentItem, FacilitySearchItem


router = APIRouter(prefix="/facilities", tags=["Facilities"])


@router.get("/search", response_model=list[FacilitySearchItem])
async def search_facilities(
    q: str = Query(..., min_length=1, description="역/정류장 이름 또는 외부 코드"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    pattern = f"%{q.strip()}%"
    stmt = (
        select(Facility)
        .where(
            or_(
                Facility.standard_name.like(pattern),
                Facility.station_name.like(pattern),
                Facility.external_code.like(pattern),
            )
        )
        .order_by(Facility.facility_type, Facility.standard_name)
        .limit(limit)
    )
    facilities = (await db.execute(stmt)).scalars().all()
    return [FacilitySearchItem.model_validate(f, from_attributes=True) for f in facilities]


@router.get("/{facility_id}/equipment", response_model=list[EquipmentItem])
async def get_facility_equipment(
    facility_id: int,
    db: AsyncSession = Depends(get_db),
):
    facility = await db.get(Facility, facility_id)
    if facility is None:
        raise HTTPException(status_code=404, detail="시설을 찾을 수 없습니다.")

    equipment_rows = (
        await db.execute(
            select(FacilityEquipment)
            .where(FacilityEquipment.facility_id == facility_id)
            .order_by(FacilityEquipment.equipment_type, FacilityEquipment.equipment_id)
        )
    ).scalars().all()

    result: list[EquipmentItem] = []
    for item in equipment_rows:
        latest_status = (
            await db.execute(
                select(EquipmentStatus.status_code)
                .where(EquipmentStatus.equipment_id == item.equipment_id)
                .order_by(desc(EquipmentStatus.updated_at), desc(EquipmentStatus.equipment_status_id))
                .limit(1)
            )
        ).scalar_one_or_none()
        result.append(
            EquipmentItem(
                equipment_id=item.equipment_id,
                equipment_type=item.equipment_type,
                external_equipment_no=item.external_equipment_no,
                exit_no=item.exit_no,
                detail_location=item.detail_location,
                direction=item.direction,
                latest_status=latest_status,
            )
        )
    return result
