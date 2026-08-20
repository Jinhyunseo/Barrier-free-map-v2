from __future__ import annotations

from typing import Any

import networkx as nx

from app.station_routing_v2.elevator_status_service import (
    get_facility_status_summary,
)
from app.station_routing_v2.path_finder import (
    find_internal_route,
)


def collect_elevator_facility_ids(
    graph: nx.DiGraph,
) -> list[str]:
    """
    그래프에 포함된 ELEVATOR edge의 facility_id를 수집한다.

    graph_loader / graph_merge에서 WALK, ELEVATOR가
    양방향 edge로 만들어질 수 있으므로 set으로 중복 제거한다.
    """

    facility_ids: set[str] = set()

    for _, _, data in graph.edges(data=True):

        mode = str(
            data.get(
                "mode",
                "",
            )
        ).strip().upper()

        if mode != "ELEVATOR":
            continue

        facility_id = data.get(
            "facility_id"
        )

        if facility_id is None:
            continue

        facility_id = str(
            facility_id
        ).strip()

        if not facility_id:
            continue

        facility_ids.add(
            facility_id
        )

    return sorted(
        facility_ids
    )


def collect_route_elevator_facility_ids(
    route_result: dict[str, Any],
) -> list[str]:
    """
    이미 탐색된 경로 결과의 edge_path에서
    실제 사용되는 ELEVATOR facility_id만 수집한다.

    전체 역 그래프의 모든 엘리베이터를 검사할 필요가 없는 경우
    사용할 수 있는 보조 함수.
    """

    facility_ids: set[str] = set()

    edge_path = route_result.get(
        "edge_path",
        [],
    )

    if not isinstance(
        edge_path,
        list,
    ):
        return []

    for edge in edge_path:

        if not isinstance(
            edge,
            dict,
        ):
            continue

        mode = str(
            edge.get(
                "mode",
                "",
            )
        ).strip().upper()

        if mode != "ELEVATOR":
            continue

        facility_id = edge.get(
            "facility_id"
        )

        if facility_id is None:
            continue

        facility_id = str(
            facility_id
        ).strip()

        if facility_id:
            facility_ids.add(
                facility_id
            )

    return sorted(
        facility_ids
    )


def find_realtime_internal_route(
    graph: nx.DiGraph,
    station_name: str,
    start_node: str,
    end_node: str,
) -> dict[str, Any]:
    """
    실시간 승강기 운행 상태를 반영하여
    역사 내부 경로를 탐색한다.

    처리 과정:

    1. 그래프의 ELEVATOR facility_id 수집
    2. 해당 역의 승강기 데이터 조회
    3. facility_id ↔ elevatorNo 직접 매칭
    4. UNAVAILABLE 승강기를 blocked 처리
    5. 신형 path_finder로 경로 탐색
    6. 실시간 상태 메타데이터를 결과에 추가

    정책:

    AVAILABLE
        경로 탐색에서 사용 가능

    UNAVAILABLE
        blocked_facility_ids에 포함하여 제외

    UNKNOWN
        상태를 알 수 없는 시설
        경로에서는 차단하지 않음
    """

    # ==================================================
    # 1. ELEVATOR facility_id 수집
    # ==================================================

    facility_ids = (
        collect_elevator_facility_ids(
            graph
        )
    )

    # ==================================================
    # 2. 실시간 상태 조회
    # ==================================================

    status_summary = (
        get_facility_status_summary(
            station_name=station_name,
            facility_ids=facility_ids,
        )
    )

    blocked_facility_ids = list(
        status_summary.get(
            "blocked_facility_ids",
            [],
        )
    )

    unknown_facility_ids = list(
        status_summary.get(
            "unknown_facility_ids",
            [],
        )
    )

    checked_facility_ids = list(
        status_summary.get(
            "checked_facility_ids",
            [],
        )
    )

    available_facility_ids = list(
        status_summary.get(
            "available_facility_ids",
            [],
        )
    )

    # ==================================================
    # 3. 실시간 고장 시설을 제외하고 경로 탐색
    # ==================================================

    result = (
        find_internal_route(
            graph=graph,
            start_node=start_node,
            end_node=end_node,
            blocked_facility_ids=(
                blocked_facility_ids
            ),
        )
    )

    # ==================================================
    # 4. 실시간 메타데이터 추가
    # ==================================================

    result[
        "realtime_status"
    ] = status_summary.get(
        "status",
        "UNKNOWN",
    )

    result[
        "checked_facility_ids"
    ] = checked_facility_ids

    result[
        "available_facility_ids"
    ] = available_facility_ids

    result[
        "blocked_facility_ids"
    ] = blocked_facility_ids

    result[
        "unknown_facility_ids"
    ] = unknown_facility_ids

    result[
        "facility_statuses"
    ] = status_summary.get(
        "facility_statuses",
        [],
    )

    result[
        "realtime_data_source"
    ] = status_summary.get(
        "data_source"
    )

    result[
        "realtime_updated_at"
    ] = status_summary.get(
        "updated_at"
    )

    return result