from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.core.database import get_sessionmaker
from app.models.models import (
    EquipmentStatus,
    Facility,
    FacilityEquipment,
    FacilityStatus,
    Transportation,
    User,
)


from app.core.data_paths import (
    BUS_ROUTES_FILE,
    BUS_STOPS_FILE,
    STATION_FACILITIES_FILE,
    STATION_REALTIME_CURRENT_DIR,
)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_list(path: Path) -> list[dict[str, Any]]:
    data = _read_json(path)
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def _station_facility_dataset() -> list[dict[str, Any]]:
    return _read_list(STATION_FACILITIES_FILE)


def _bus_stop_dataset() -> list[dict[str, Any]]:
    return _read_list(BUS_STOPS_FILE)


def _bus_route_dataset() -> list[dict[str, Any]]:
    return _read_list(BUS_ROUTES_FILE)


def _realtime_datasets() -> list[dict[str, Any]]:
    datasets: list[dict[str, Any]] = []
    for path in sorted(STATION_REALTIME_CURRENT_DIR.glob("*.json")):
        data = _read_json(path)
        if isinstance(data, dict) and isinstance(data.get("items"), dict):
            datasets.append(data)
    return datasets


def _to_float(value: Any) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _map_realtime_status(value: Any) -> str:
    text = str(value or "").strip()
    if any(keyword in text for keyword in ("운행중", "정상")):
        return "NORMAL"
    if any(keyword in text for keyword in ("점검", "검사", "정비")):
        return "MAINTENANCE"
    if any(keyword in text for keyword in ("고장", "정지", "중지", "불가")):
        return "BROKEN"
    return "UNKNOWN"


async def seed_user(session) -> None:
    user = await session.get(User, 1)
    if user is None:
        session.add(User(user_id=1, email="demo@barrier-free.local", nickname="프로토타입 사용자"))
        await session.flush()


async def seed_transportation(session) -> int:
    count = 0

    # 버스 노선
    for row in _bus_route_dataset():
        external_code = str(row.get("노선ID") or "").strip()
        if not external_code:
            continue
        existing = (
            await session.execute(
                select(Transportation).where(
                    Transportation.transport_type == "BUS",
                    Transportation.external_code == external_code,
                )
            )
        ).scalar_one_or_none()
        if existing:
            continue
        session.add(
            Transportation(
                transport_type="BUS",
                route_number=str(row.get("노선명") or "").strip() or None,
                external_code=external_code,
                operator_name=str(row.get("운수회사명") or "").strip() or None,
                is_low_floor=None,
                start_name=str(row.get("기점정류장명") or "").strip() or None,
                end_name=str(row.get("종점정류장명") or "").strip() or None,
            )
        )
        count += 1

    # 지하철 노선도 transportation에 함께 보관합니다.
    # 역사 데이터의 운영기관 코드 + 노선 코드를 외부 식별자로 사용해 재실행 시 중복되지 않습니다.
    seen_subway: set[str] = set()
    for row in _station_facility_dataset():
        operator = str(row.get("railOprIsttCd") or "").strip()
        line_code = str(row.get("lnCd") or "").strip()
        if not line_code:
            continue
        external_code = f"{operator}:{line_code}"
        if external_code in seen_subway:
            continue
        seen_subway.add(external_code)

        existing = (
            await session.execute(
                select(Transportation).where(
                    Transportation.transport_type == "SUBWAY",
                    Transportation.external_code == external_code,
                )
            )
        ).scalar_one_or_none()
        if existing:
            continue

        session.add(
            Transportation(
                transport_type="SUBWAY",
                route_number=line_code,
                external_code=external_code,
                operator_name=operator or None,
                is_low_floor=None,
            )
        )
        count += 1

    await session.flush()
    return count


async def seed_bus_stops(session) -> int:
    count = 0
    for row in _bus_stop_dataset():
        external_code = str(row.get("정류장번호") or "").strip()
        name = str(row.get("정류장명") or "").strip()
        if not external_code or not name:
            continue
        facility = (
            await session.execute(
                select(Facility).where(
                    Facility.facility_type == "BUS_STOP",
                    Facility.external_code == external_code,
                )
            )
        ).scalar_one_or_none()
        if facility is None:
            detail = str(row.get("상세위치") or "").strip()
            facility = Facility(
                facility_type="BUS_STOP",
                standard_name=name,
                station_name=None,
                line_name=str(row.get("시내버스_경유노선번호") or "").strip()[:100] or None,
                external_code=external_code,
                address=detail or None,
                latitude=_to_float(row.get("위도")),
                longitude=_to_float(row.get("경도")),
            )
            session.add(facility)
            await session.flush()
            session.add(
                FacilityStatus(
                    facility_id=facility.facility_id,
                    status_code="UNKNOWN",
                    source="SEED_BUS_STOP",
                    detail="정적 정류장 정보만 있어 현재 운행/접근 상태는 UNKNOWN으로 초기화",
                )
            )
            count += 1
    await session.flush()
    return count


async def seed_stations_and_equipment(session) -> tuple[int, int]:
    station_count = 0
    equipment_count = 0

    for row in _station_facility_dataset():
        operator = str(row.get("railOprIsttCd") or "").strip()
        line_code = str(row.get("lnCd") or "").strip()
        station_code = str(row.get("stinCd") or "").strip()
        station_name = str(row.get("stinNm") or "").strip()
        external_code = f"{operator}:{line_code}:{station_code}"

        if not station_code:
            continue
        if not station_name:
            station_name = f"역 코드 {station_code}"

        facility = (
            await session.execute(
                select(Facility).where(
                    Facility.facility_type == "STATION",
                    Facility.external_code == external_code,
                )
            )
        ).scalar_one_or_none()

        if facility is None:
            facility = Facility(
                facility_type="STATION",
                standard_name=station_name,
                station_name=station_name,
                line_name=line_code or None,
                external_code=external_code,
            )
            session.add(facility)
            await session.flush()
            session.add(
                FacilityStatus(
                    facility_id=facility.facility_id,
                    status_code="UNKNOWN",
                    source="SEED_STATION",
                    detail="정적 역사 정보만 있어 현재 시설 상태는 UNKNOWN으로 초기화",
                )
            )
            station_count += 1

        for equipment_type, key in (("ELEVATOR", "elevators"), ("ESCALATOR", "escalators")):
            for index, item in enumerate(row.get(key, []) or [], start=1):
                external_no = str(item.get("elevatorNo") or "").strip()
                if not external_no:
                    external_no = f"STATIC:{external_code}:{equipment_type}:{index}"

                existing = (
                    await session.execute(
                        select(FacilityEquipment).where(
                            FacilityEquipment.facility_id == facility.facility_id,
                            FacilityEquipment.equipment_type == equipment_type,
                            FacilityEquipment.external_equipment_no == external_no,
                        )
                    )
                ).scalar_one_or_none()
                if existing:
                    continue

                equipment = FacilityEquipment(
                    facility_id=facility.facility_id,
                    equipment_type=equipment_type,
                    external_equipment_no=external_no,
                    exit_no=str(item.get("exitNo") or "").strip() or None,
                    detail_location=str(item.get("dtlLoc") or "").strip() or None,
                    direction=str(item.get("updnDvNm") or "").strip() or None,
                    from_floor=str(item.get("runStinFlorFr") or "").strip() or None,
                    to_floor=str(item.get("runStinFlorTo") or "").strip() or None,
                    capacity_persons=item.get("rglnPsno") if isinstance(item.get("rglnPsno"), int) else None,
                    capacity_kg=item.get("rglnWgt") if isinstance(item.get("rglnWgt"), int) else None,
                )
                session.add(equipment)
                await session.flush()
                session.add(
                    EquipmentStatus(
                        equipment_id=equipment.equipment_id,
                        status_code="UNKNOWN",
                        source="STATIC_DATA",
                        detail="정적 시설 데이터에는 실시간 운행상태가 없어 UNKNOWN으로 초기화",
                    )
                )
                equipment_count += 1

    await session.flush()
    return station_count, equipment_count


async def seed_realtime_equipment_status(session) -> int:
    count = 0
    all_items: list[tuple[str, str, dict[str, Any]]] = []

    for data in _realtime_datasets():
        items = data.get("items", {})
        updated_at = str(data.get("updated_at") or "")
        for key, values in items.items():
            equipment_type = "ELEVATOR" if "엘리베이터" in key else "ESCALATOR"
            for item in values or []:
                if isinstance(item, dict):
                    all_items.append((equipment_type, updated_at, item))

    for equipment_type, updated_at, item in all_items:
        station_code = str(item.get("locationStinCd") or "").strip()
        line_code = str(item.get("locationLnCd") or "").strip()
        external_no = str(item.get("elevatorNo") or "").strip()
        if not external_no:
            continue

        facility = None
        if station_code not in {"", "-"}:
            facilities = (
                await session.execute(
                    select(Facility).where(Facility.facility_type == "STATION")
                )
            ).scalars().all()
            facility = next(
                (
                    f for f in facilities
                    if f.external_code
                    and f.external_code.endswith(f":{station_code}")
                    and (line_code in {"", "-"} or f":{line_code}:" in f.external_code)
                ),
                None,
            )

        stmt = select(FacilityEquipment).where(
            FacilityEquipment.equipment_type == equipment_type,
            FacilityEquipment.external_equipment_no == external_no,
        )
        if facility is not None:
            stmt = stmt.where(FacilityEquipment.facility_id == facility.facility_id)
        equipment = (await session.execute(stmt.limit(1))).scalars().first()

        if equipment is None and facility is not None:
            equipment = FacilityEquipment(
                facility_id=facility.facility_id,
                equipment_type=equipment_type,
                external_equipment_no=external_no,
                exit_no=str(item.get("locationExitNo") or "").strip() or None,
                detail_location=str(item.get("dtlLoc") or "").strip() or None,
                direction=str(item.get("locationUpdnDvNm") or "").strip() or None,
            )
            session.add(equipment)
            await session.flush()

        if equipment is None:
            continue

        # 같은 source/detail 상태가 이미 있으면 재실행 시 중복 추가하지 않습니다.
        status_code = _map_realtime_status(item.get("elvtrStts"))
        detail = f"{item.get('elvtrStts') or ''} / snapshot={updated_at}".strip()
        existing_status = (
            await session.execute(
                select(EquipmentStatus).where(
                    EquipmentStatus.equipment_id == equipment.equipment_id,
                    EquipmentStatus.source == "REALTIME_SNAPSHOT",
                    EquipmentStatus.detail == detail,
                )
            )
        ).scalar_one_or_none()
        if existing_status:
            continue

        try:
            observed_at = datetime.fromisoformat(updated_at) if updated_at else None
        except ValueError:
            observed_at = None

        status_row = EquipmentStatus(
            equipment_id=equipment.equipment_id,
            status_code=status_code,
            source="REALTIME_SNAPSHOT",
            detail=detail,
        )
        if observed_at is not None:
            # 실제 스냅샷 시각을 보존해 최신 상태 조회가 데이터 수집 시점을 기준으로 동작하게 합니다.
            status_row.updated_at = observed_at
        session.add(status_row)
        count += 1

    await session.flush()
    return count


async def main() -> None:
    async with get_sessionmaker()() as session:
        await seed_user(session)
        routes = await seed_transportation(session)
        bus_stops = await seed_bus_stops(session)
        stations, equipment = await seed_stations_and_equipment(session)
        realtime = await seed_realtime_equipment_status(session)
        await session.commit()

    print("Seed completed")
    print(f"- transportation inserted: {routes}")
    print(f"- bus stops inserted: {bus_stops}")
    print(f"- stations inserted: {stations}")
    print(f"- station equipment inserted: {equipment}")
    print(f"- realtime equipment statuses inserted: {realtime}")
    print("- demo user ensured: user_id=1")


if __name__ == "__main__":
    asyncio.run(main())
