from __future__ import annotations

import asyncio
from urllib.parse import urlsplit

from sqlalchemy import func, select, text

from app.core.config import settings
from app.core.database import get_sessionmaker
from app.models.models import (
    EquipmentStatus,
    Facility,
    FacilityEquipment,
    Report,
    Transportation,
    User,
)


def _safe_db_target(url: str) -> str:
    try:
        parsed = urlsplit(url.replace("mysql+asyncmy://", "mysql://").replace("sqlite+aiosqlite://", "sqlite://"))
        if parsed.scheme.startswith("sqlite"):
            return "SQLite local database"
        return f"{parsed.scheme}://{parsed.hostname or '?'}:{parsed.port or '?'}{parsed.path}"
    except Exception:
        return "configured database"


async def main() -> None:
    print("Barrier-Free deployment preflight")
    print(f"- DB target: {_safe_db_target(settings.DATABASE_URL)}")
    print(f"- Gemini key configured: {'YES' if bool(settings.GEMINI_API_KEY) else 'NO'}")
    print(f"- Gemini model: {settings.REPORT_GEMINI_MODEL}")
    print(f"- AI accept threshold: {settings.REPORT_AI_ACCEPT_THRESHOLD}")

    async with get_sessionmaker()() as session:
        await session.execute(text("SELECT 1"))
        print("- Database connection: OK")

        tables = [
            ("user", User),
            ("transportation", Transportation),
            ("facility", Facility),
            ("facility_equipment", FacilityEquipment),
            ("equipment_status", EquipmentStatus),
            ("reports", Report),
        ]
        for label, model in tables:
            count = (await session.execute(select(func.count()).select_from(model))).scalar_one()
            print(f"- {label}: {count}")

        station_count = (
            await session.execute(
                select(func.count()).select_from(Facility).where(Facility.facility_type == "STATION")
            )
        ).scalar_one()
        bus_stop_count = (
            await session.execute(
                select(func.count()).select_from(Facility).where(Facility.facility_type == "BUS_STOP")
            )
        ).scalar_one()
        elevator_count = (
            await session.execute(
                select(func.count()).select_from(FacilityEquipment).where(
                    FacilityEquipment.equipment_type == "ELEVATOR"
                )
            )
        ).scalar_one()
        escalator_count = (
            await session.execute(
                select(func.count()).select_from(FacilityEquipment).where(
                    FacilityEquipment.equipment_type == "ESCALATOR"
                )
            )
        ).scalar_one()

        print(f"- stations: {station_count}")
        print(f"- bus stops: {bus_stop_count}")
        print(f"- elevators: {elevator_count}")
        print(f"- escalators: {escalator_count}")

    print("Preflight completed successfully.")


if __name__ == "__main__":
    asyncio.run(main())
