from __future__ import annotations

from pathlib import Path

from app.core.config import BACKEND_DIR


# 모든 정적/스냅샷 데이터의 단일 루트
DATA_DIR = BACKEND_DIR / "app" / "data"

# 버스/정류장
BUS_DATA_DIR = DATA_DIR / "bus"
BUS_STOPS_FILE = BUS_DATA_DIR / "bus_stops.json"
BUS_ROUTES_FILE = BUS_DATA_DIR / "bus_routes.json"

# 보행망
WALKING_DATA_DIR = DATA_DIR / "walking"
WALKING_NETWORK_FILE = WALKING_DATA_DIR / "seongnam_walking_network.geojson"

# 역사/시설
STATIONS_DATA_DIR = DATA_DIR / "stations"
STATION_FACILITIES_DIR = STATIONS_DATA_DIR / "facilities"
STATION_FACILITIES_FILE = STATION_FACILITIES_DIR / "station_facilities.json"
STATION_FACILITIES_BY_LINE_DIR = STATION_FACILITIES_DIR / "by_line"
STATION_FACILITIES_LEGACY_DIR = STATION_FACILITIES_DIR / "legacy"

# 역사 내 경로 그래프
STATION_GRAPHS_DIR = STATIONS_DATA_DIR / "graphs"
STATION_GRAPHS_V1_DIR = STATION_GRAPHS_DIR / "v1"
STATION_GRAPHS_V1_FILE = STATION_GRAPHS_V1_DIR / "all_stations_graph.json"
STATION_GRAPHS_V1_INDIVIDUAL_DIR = STATION_GRAPHS_V1_DIR / "individual"
STATION_GRAPHS_V2_DIR = STATION_GRAPHS_DIR / "v2"

# 실시간/스냅샷 장비 상태
STATION_REALTIME_DIR = STATIONS_DATA_DIR / "realtime"
STATION_REALTIME_CURRENT_DIR = STATION_REALTIME_DIR / "current"
STATION_REALTIME_ARCHIVE_DIR = STATION_REALTIME_DIR / "archive"


def ensure_data_directories() -> None:
    """런타임에서 생성되는 데이터 폴더가 없을 때 안전하게 생성합니다."""
    for path in (
        BUS_DATA_DIR,
        WALKING_DATA_DIR,
        STATION_FACILITIES_DIR,
        STATION_FACILITIES_BY_LINE_DIR,
        STATION_GRAPHS_V1_DIR,
        STATION_GRAPHS_V1_INDIVIDUAL_DIR,
        STATION_GRAPHS_V2_DIR,
        STATION_REALTIME_CURRENT_DIR,
        STATION_REALTIME_ARCHIVE_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)
