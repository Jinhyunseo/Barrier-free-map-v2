from __future__ import annotations

from typing import Any

from .moran import STATION_GRAPH_CONFIG as MORAN_CONFIG
from .pangyo import STATION_GRAPH_CONFIG as PANGYO_CONFIG
from .seongnam import STATION_GRAPH_CONFIG as SEONGNAM_CONFIG
from .yatap import STATION_GRAPH_CONFIG as YATAP_CONFIG


_CONFIGS = {
    config["station_name"]: config
    for config in (
        MORAN_CONFIG,
        PANGYO_CONFIG,
        SEONGNAM_CONFIG,
        YATAP_CONFIG,
    )
}


def get_station_graph_config(station_name: str) -> dict[str, Any]:
    """역 이름에 해당하는 수동 역사 그래프 설정을 반환합니다.

    별도 수동 설정이 없는 역은 빈 dict를 반환하여 자동 빌더가
    기본 시설/메타데이터만으로 계속 동작할 수 있게 합니다.
    """
    normalized = str(station_name or "").strip()
    if normalized and not normalized.endswith("역"):
        normalized += "역"
    return _CONFIGS.get(normalized, {})
