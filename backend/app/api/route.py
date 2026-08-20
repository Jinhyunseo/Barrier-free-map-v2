from typing import Any

from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.schemas.route_schema import (
    RouteByPlaceRequest,
    RouteCandidateRequest,
)

from app.services.geocode_service import (
    GeocodeService,
)

from app.services.kakao_service import (
    get_transit_routes,
    simplify_routes,
)

from app.services.movement_extraction_service import (
    attach_station_movements,
)

from app.services.recommendation_service import (
    select_best_candidate,
)

from app.services.station_path_service import (
    analyze_station_movement,
    resolve_movement_nodes,
    find_shortest_internal_path,
    extract_required_facilities,
    find_realtime_safe_internal_path,
)

from app.services.facility_status_service import (
    attach_realtime_status_to_facilities,
    summarize_route_facility_status,
)

from app.services.bus_matching_service import (
    match_bus_step_identifiers,
)

from app.services.bus_arrival_service import (
    get_low_floor_bus_status,
)
from app.services.walking_route_service import (
    get_walking_route,
)
from app.services.walking_integration_service import (
    attach_walking_access_to_routes,
)
from app.station_routing_v2.graph_merge import (
    build_station_graph_from_directory,
)

from app.station_routing_v2.path_finder import (
    find_internal_route,
)

router = APIRouter(
    prefix="/routes",
    tags=["Routes"],
)
# ==============================================================================
# 신형 역사 그래프 V2 설정
# ==============================================================================

STATION_GRAPHS_V2_DIR = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "station_graphs_v2"
)


TRANSFER_STATION_CONFIG = {
    "이매": {
        "folder": "imae",
        "parent_station_code": "IMA",
    },
    "정자": {
        "folder": "jeongja",
        "parent_station_code": "JJA",
    },
    "미금": {
        "folder": "migeum",
        "parent_station_code": "MIG",
    },
    "모란": {
        "folder": "moran",
        "parent_station_code": "MOR",
    },
    "판교": {
        "folder": "pangyo",
        "parent_station_code": "PYO",
    },
}


def _normalize_station_text(
    value: Any,
) -> str:
    """
    역명/방향역 비교를 위한 간단한 정규화.
    """

    return (
        str(value or "")
        .replace("역", "")
        .replace(" ", "")
        .strip()
    )


def _find_v2_platform_node(
    graph: Any,
    direction_station: str | None,
) -> str | None:
    """
    direction_station을 이용해
    신형 그래프의 PLATFORM node를 찾는다.

    예:
        판교 -> IMA_GG_PLATFORM_PANGYO
        서현 -> IMA_PLATFORM_SEOHYEON
    """

    target = _normalize_station_text(
        direction_station
    )

    if not target:
        return None

    candidates: list[str] = []

    for node_id, node_data in graph.nodes(
        data=True
    ):
        node_type = str(
            node_data.get(
                "type",
                "",
            )
        ).upper()

        # 일부 JSON에서 type 필드가 없더라도
        # node id의 PLATFORM 표기를 이용할 수 있게 한다.
        is_platform = (
            node_type == "PLATFORM"
            or "PLATFORM" in str(node_id).upper()
        )

        if not is_platform:
            continue

        node_name = _normalize_station_text(
            node_data.get(
                "name",
                "",
            )
        )

        if target in node_name:
            candidates.append(
                str(node_id)
            )

    # 정확히 하나일 때만 사용한다.
    # 애매한 경우 임의 선택하지 않는다.
    if len(candidates) == 1:
        return candidates[0]

    return None


def _build_v2_transfer_internal_path(
    movement: dict[str, Any],
) -> dict[str, Any] | None:
    """
    TRANSFER movement 하나를 신형 역사 그래프로 계산한다.

    실시간 승강기 운행 여부는 사용하지 않는다.
    """

    station_name = (
        _normalize_station_text(
            movement.get(
                "station_name"
            )
        )
    )

    config = TRANSFER_STATION_CONFIG.get(
        station_name
    )

    # 아직 V2 그래프가 없는 환승역
    if not config:
        return None

    station_directory = (
        STATION_GRAPHS_V2_DIR
        / config["folder"]
    )

    graph = (
        build_station_graph_from_directory(
            station_directory,
            config[
                "parent_station_code"
            ],
        )
    )

    # 환승 전 열차가 들어온 방향
    # -> 현재 승강장 판별
    start_node = (
        _find_v2_platform_node(
            graph,
            movement.get(
                "arrival_direction_station"
            ),
        )
    )

    # 환승 후 열차가 출발하는 방향
    # -> 환승할 승강장 판별
    end_node = (
        _find_v2_platform_node(
            graph,
            movement.get(
                "departure_direction_station"
            ),
        )
    )

    if (
        not start_node
        or not end_node
    ):
        return {
            "status": "NODE_NOT_FOUND",
            "movement": movement,
            "start_node": start_node,
            "end_node": end_node,
            "node_path": [],
            "edge_path": [],
            "steps": [],
            "required_facilities": [],
        }

    result = (
        find_internal_route(
            graph,
            start_node,
            end_node,
        )
    )

    # path_finder 결과를 복사해서
    # API 응답용 데이터를 추가한다.
    result = dict(result)

    result["movement"] = movement

    # --------------------------------------------------------------------------
    # 경로에서 사용한 엘리베이터 추출
    #
    # 실시간 상태는 연결하지 않는다.
    # --------------------------------------------------------------------------

    required_facilities: list[
        dict[str, Any]
    ] = []

    seen_facility_ids: set[str] = set()

    for edge in result.get(
        "edge_path",
        [],
    ):
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
        ).upper()

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

        if not facility_id:
            continue

        if facility_id in seen_facility_ids:
            continue

        seen_facility_ids.add(
            facility_id
        )

        required_facilities.append(
            {
                "facility_id": facility_id,
                "facility_type": "ELEVATOR",

                # 현재 버전에서는 실시간 운행 여부를
                # 경로 계산에 사용하지 않는다.
                "realtime": {
                    "realtime_status": (
                        "UNKNOWN"
                    )
                },
            }
        )

    result[
        "required_facilities"
    ] = required_facilities

    return result


def _attach_v2_internal_paths(
    recommendation_result: dict[str, Any],
) -> None:
    """
    최종 추천 경로에 신형 환승역 내부 경로를 추가한다.

    기존 internal_paths는 건드리지 않고
    internal_paths_v2라는 별도 필드에 저장한다.
    """

    recommended_route = (
        recommendation_result.get(
            "recommended_route"
        )
    )

    if not isinstance(
        recommended_route,
        dict,
    ):
        return

    station_movements = (
        recommended_route.get(
            "station_movements",
            [],
        )
    )

    if not isinstance(
        station_movements,
        list,
    ):
        recommended_route[
            "internal_paths_v2"
        ] = []

        return

    internal_paths_v2: list[
        dict[str, Any]
    ] = []

    for movement in station_movements:

        if not isinstance(
            movement,
            dict,
        ):
            continue

        movement_type = str(
            movement.get(
                "movement_type",
                "",
            )
        ).upper()

        # 현재 MVP에서는 환승만 V2 그래프로 처리
        if movement_type != "TRANSFER":
            continue

        try:
            internal_path = (
                _build_v2_transfer_internal_path(
                    movement
                )
            )

            if internal_path is not None:
                internal_paths_v2.append(
                    internal_path
                )

        except Exception as error:
            # V2 화면용 경로 계산 실패 때문에
            # 기존 추천 API 전체가 실패하면 안 된다.
            internal_paths_v2.append(
                {
                    "status": "ERROR",
                    "movement": movement,
                    "message": str(error),
                    "node_path": [],
                    "edge_path": [],
                    "steps": [],
                    "required_facilities": [],
                }
            )

    recommended_route[
        "internal_paths_v2"
    ] = internal_paths_v2

# ==============================================================================
# 1. 좌표 기반 후보 경로 조회
# ==============================================================================

@router.post("/candidates")
async def get_route_candidates(
    request: RouteCandidateRequest,
) -> dict[str, Any]:
    """
    출발지와 목적지 좌표를 직접 입력받아
    카카오 후보 경로 전체를 반환합니다.
    """

    try:
        kakao_data = (
            await get_transit_routes(
                origin_x=request.origin_x,
                origin_y=request.origin_y,
                destination_x=request.destination_x,
                destination_y=request.destination_y,
            )
        )

        return simplify_routes(
            kakao_data
        )

    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=(
                "카카오 후보 경로 조회 중 "
                f"오류가 발생했습니다: {error}"
            ),
        ) from error


# ==============================================================================
# 2. 장소명 기반 후보 경로 조회
# ==============================================================================

@router.post("/by-places")
async def get_routes_by_places(
    request: RouteByPlaceRequest,
) -> dict[str, Any]:
    """
    출발지·목적지 장소명을 좌표로 변환한 뒤
    카카오 후보 경로 전체를 반환합니다.

    각 후보에는 station_movements도 추가합니다.
    """

    geocode_service = (
        GeocodeService()
    )

    # --------------------------------------------------------------------------
    # 1. 출발지 검색
    # --------------------------------------------------------------------------

    _, origin_results = (
        await geocode_service.search_auto(
            request.origin_name
        )
    )

    if not origin_results:
        raise HTTPException(
            status_code=404,
            detail=(
                "출발지를 찾을 수 없습니다: "
                f"{request.origin_name}"
            ),
        )

    # --------------------------------------------------------------------------
    # 2. 목적지 검색
    # --------------------------------------------------------------------------

    _, destination_results = (
        await geocode_service.search_auto(
            request.destination_name
        )
    )

    if not destination_results:
        raise HTTPException(
            status_code=404,
            detail=(
                "목적지를 찾을 수 없습니다: "
                f"{request.destination_name}"
            ),
        )

    origin = (
        origin_results[0]
    )

    destination = (
        destination_results[0]
    )

    # --------------------------------------------------------------------------
    # 3. 카카오 후보 경로 조회
    # --------------------------------------------------------------------------

    try:
        kakao_data = (
            await get_transit_routes(
                origin_x=origin.longitude,
                origin_y=origin.latitude,
                destination_x=destination.longitude,
                destination_y=destination.latitude,
            )
        )

    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=(
                "카카오 후보 경로 조회 중 "
                f"오류가 발생했습니다: {error}"
            ),
        ) from error

    # --------------------------------------------------------------------------
    # 4. 응답 단순화
    # --------------------------------------------------------------------------

    simplified_data = simplify_routes(
        kakao_data
    )

    routes = simplified_data["routes"]

    routes = await attach_walking_access_to_routes(
        routes=routes,

        origin_x=origin.longitude,
        origin_y=origin.latitude,

        destination_x=destination.longitude,
        destination_y=destination.latitude,

        origin_name=request.origin_name,
        destination_name=request.destination_name,

        avoid_stairs=(
            request.mobility_constraints.avoid_stairs
        ),
    )

    result = await select_best_candidate(
        routes=routes,
        mobility_constraints=(
            request.mobility_constraints.model_dump()
        ),
        route_preference=(
            request.route_preference
        ),
    )

    # --------------------------------------------------------------------------
    # 5. 승차 / 환승 / 하차 movement 추출
    # --------------------------------------------------------------------------

    routes = (
        attach_station_movements(
            routes
        )
    )

    # --------------------------------------------------------------------------
    # 6. 반환
    # --------------------------------------------------------------------------

    return {
        "origin": (
            origin.model_dump()
        ),

        "destination": (
            destination.model_dump()
        ),

        "mobility_constraints": (
            request.mobility_constraints.model_dump()
        ),

        "route_preference": (
            request.route_preference
        ),

        **simplified_data,

        "routes": (
            routes
        ),
    }


# ==============================================================================
# 3. 최종 사용자 맞춤 경로 추천
# ==============================================================================

@router.post("/recommend")
async def get_recommended_route(
    request: RouteByPlaceRequest,
) -> dict[str, Any]:
    """
    최종 사용자 맞춤 경로 추천 API.

    처리 과정:

    1. 장소명 → 좌표 변환
    2. 카카오 대중교통 후보 경로 조회
    3. 후보 경로 단순화
    4. station_movements 추출
    5. 역 내부 이동 그래프 탐색
    6. 이동 조건 제약 적용
    7. 실제 EV / ES 실시간 상태 조회
    8. 고장 시설 발견 시 해당 edge 차단
    9. 역 내부 우회 경로 재탐색
    10. Hard Barrier 검사
    11. 경로 선호도 기반 점수 계산
    12. 가장 적합한 경로 추천
    """

    geocode_service = (
        GeocodeService()
    )

    # ==========================================================================
    # 1. 출발지 검색
    # ==========================================================================

    _, origin_results = (
        await geocode_service.search_auto(
            request.origin_name
        )
    )

    if not origin_results:
        raise HTTPException(
            status_code=404,
            detail=(
                "출발지를 찾을 수 없습니다: "
                f"{request.origin_name}"
            ),
        )

    # ==========================================================================
    # 2. 목적지 검색
    # ==========================================================================

    _, destination_results = (
        await geocode_service.search_auto(
            request.destination_name
        )
    )

    if not destination_results:
        raise HTTPException(
            status_code=404,
            detail=(
                "목적지를 찾을 수 없습니다: "
                f"{request.destination_name}"
            ),
        )

    origin = (
        origin_results[0]
    )

    destination = (
        destination_results[0]
    )

    # ==========================================================================
    # 3. 카카오 후보 경로 조회
    # ==========================================================================

    try:
        kakao_data = (
            await get_transit_routes(
                origin_x=origin.longitude,
                origin_y=origin.latitude,
                destination_x=destination.longitude,
                destination_y=destination.latitude,
            )
        )

    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=(
                "카카오 후보 경로 조회 중 "
                f"오류가 발생했습니다: {error}"
            ),
        ) from error

    # ==========================================================================
    # 4. 카카오 응답 단순화
    # ==========================================================================

    simplified_data = (
        simplify_routes(
            kakao_data
        )
    )

    routes = (
        simplified_data.get(
            "routes",
            [],
        )
    )

    if not routes:
        raise HTTPException(
            status_code=404,
            detail=(
                "조회된 후보 경로가 없습니다."
            ),
        )
    # ==========================================================================
    # 5. 출발지/목적지 보행 경로 연결
    # ==========================================================================

    try:
        routes = await attach_walking_access_to_routes(
            routes=routes,

            origin_x=origin.longitude,
            origin_y=origin.latitude,

            destination_x=destination.longitude,
            destination_y=destination.latitude,

            origin_name=request.origin_name,
            destination_name=request.destination_name,

            avoid_stairs=(
                request.mobility_constraints.avoid_stairs
            ),

            # TMAP 호출 전 후보 3개를
            # 사용자의 경로 선호도에 따라 선별
            route_preference=request.route_preference,
        )

    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=(
                "보행 경로 연결 중 "
                f"오류가 발생했습니다: {error}"
            ),
        ) from error

    # ==========================================================================
    # 5. station_movements 추출
    # ==========================================================================

    routes = (
        attach_station_movements(
            routes
        )
    )

    # ==========================================================================
    # 6. 최종 추천
    #
    # recommendation_service 내부에서:
    #
    # station_movements
    # → 역 내부 그래프
    # → 이동 조건 제약
    # → 실시간 EV / ES
    # → 고장 시설 우회
    # → Hard Barrier
    # → 경로 선호도 점수
    # → 최종 추천
    #
    # 순으로 처리됩니다.
    # ==========================================================================

    try:
        recommendation_result = (
            await select_best_candidate(
                routes=routes,
                mobility_constraints=(
                    request.mobility_constraints.model_dump()
                ),
                route_preference=(
                    request.route_preference
                ),
            )
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(
                error
            ),
        ) from error

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "경로 추천에 필요한 데이터 파일을 "
                f"찾을 수 없습니다: {error}"
            ),
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "추천 경로 계산 중 "
                f"오류가 발생했습니다: {error}"
            ),
        ) from error

    # ==========================================================================
    # 7. 신형 역사 그래프 V2 환승 경로 추가
    #
    # 기존 추천 결과와 internal_paths는 그대로 유지한다.
    # 화면 표시용으로 internal_paths_v2만 추가한다.
    # ==========================================================================

    _attach_v2_internal_paths(
        recommendation_result
    )

    # ==========================================================================
    # 8. 최종 반환
    # ==========================================================================

    return {
        "origin": (
            origin.model_dump()
        ),

        "destination": (
            destination.model_dump()
        ),

        **recommendation_result,
    }

    # ==========================================================================
    # 7. 최종 반환
    # ==========================================================================

    return {
        "origin": (
            origin.model_dump()
        ),

        "destination": (
            destination.model_dump()
        ),

        **recommendation_result,
    }


# ==============================================================================
# 4. 기본 역 내부 경로 디버그
# ==============================================================================

@router.post("/debug/path")
async def debug_station_path(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    station_movement 하나의 기본 역 내부 경로를 테스트합니다.

    payload 예시:
    {
        "movement": {...},
        "mobility_constraints": {
            "avoid_stairs": true,
            "require_elevator": true,
            "avoid_escalator": false,
            "avoid_steep_slope": false
        }
    }

    실시간 상태는 반영하지 않습니다.
    """

    movement = payload.get(
        "movement"
    )

    mobility_constraints = payload.get(
        "mobility_constraints",
        {},
    )

    if not isinstance(
        movement,
        dict,
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "movement는 객체(dict) 형태여야 합니다."
            ),
        )

    if not isinstance(
        mobility_constraints,
        dict,
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "mobility_constraints는 "
                "객체(dict) 형태여야 합니다."
            ),
        )

    return (
        analyze_station_movement(
            movement=movement,
            mobility_constraints=(
                mobility_constraints
            ),
        )
    )


# ==============================================================================
# 5. 실시간 시설 상태 디버그
# ==============================================================================

@router.post(
    "/debug/facility-status"
)
async def debug_facility_status(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    required_facilities에
    실제 EV / ES 실시간 운행 상태를 붙입니다.
    """

    required_facilities = (
        payload.get(
            "required_facilities",
            [],
        )
    )

    if not isinstance(
        required_facilities,
        list,
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "required_facilities는 "
                "list 형태여야 합니다."
            ),
        )

    facilities_with_status = (
        attach_realtime_status_to_facilities(
            required_facilities
        )
    )

    summary = (
        summarize_route_facility_status(
            facilities_with_status
        )
    )

    return {
        "required_facilities": (
            facilities_with_status
        ),

        "facility_status_summary": (
            summary
        ),
    }


# ==============================================================================
# 6. 특정 시설 강제 차단 디버그
# ==============================================================================

@router.post(
    "/debug/path-with-blocked-facilities"
)
async def debug_path_with_blocked_facilities(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    특정 EV / ES를 강제로 차단하고
    이동 조건을 반영해 BFS를 수행합니다.
    """

    movement = payload.get(
        "movement"
    )

    blocked_edge_ids = payload.get(
        "blocked_edge_ids",
        [],
    )

    mobility_constraints = payload.get(
        "mobility_constraints",
        {},
    )

    if not isinstance(
        movement,
        dict,
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "movement는 객체(dict) 형태여야 합니다."
            ),
        )

    if not isinstance(
        blocked_edge_ids,
        list,
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "blocked_edge_ids는 list 형태여야 합니다."
            ),
        )

    if not isinstance(
        mobility_constraints,
        dict,
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "mobility_constraints는 "
                "객체(dict) 형태여야 합니다."
            ),
        )

    blocked_set = {
        str(
            edge_id
        ).strip()
        for edge_id
        in blocked_edge_ids
        if str(
            edge_id
        ).strip()
    }

    resolved = (
        resolve_movement_nodes(
            movement
        )
    )

    if (
        resolved.get(
            "status"
        )
        != "SUCCESS"
    ):
        return {
            "status": (
                resolved.get(
                    "status",
                    "ERROR",
                )
            ),
            "mobility_constraints": (
                mobility_constraints
            ),
            "movement": (
                movement
            ),
            "blocked_edge_ids": (
                sorted(
                    blocked_set
                )
            ),
            "node_resolution": (
                resolved
            ),
        }

    station_name = str(
        resolved[
            "station_name"
        ]
    )

    start_node = (
        resolved[
            "start_node"
        ]
    )

    end_node = (
        resolved[
            "end_node"
        ]
    )

    internal_path = (
        find_shortest_internal_path(
            station_name=station_name,
            start_node_id=str(
                start_node[
                    "id"
                ]
            ),
            end_node_id=str(
                end_node[
                    "id"
                ]
            ),
            blocked_edge_ids=(
                blocked_set
            ),
            mobility_constraints=(
                mobility_constraints
            ),
        )
    )

    required_facilities = (
        extract_required_facilities(
            internal_path
        )
    )

    return {
        "status": (
            internal_path.get(
                "status"
            )
        ),
        "mobility_constraints": (
            mobility_constraints
        ),
        "movement": (
            movement
        ),
        "blocked_edge_ids": (
            sorted(
                blocked_set
            )
        ),
        "node_resolution": (
            resolved
        ),
        "start_node": (
            start_node
        ),
        "end_node": (
            end_node
        ),
        "node_path": (
            internal_path.get(
                "node_path",
                [],
            )
        ),
        "edge_count": (
            internal_path.get(
                "edge_count",
                0,
            )
        ),
        "required_facility_count": (
            len(
                required_facilities
            )
        ),
        "required_facilities": (
            required_facilities
        ),
    }


# ==============================================================================
# 7. 이동 조건 + 실시간 EV/ES 기반 내부 경로 디버그
# ==============================================================================

@router.post(
    "/debug/realtime-safe-path"
)
async def debug_realtime_safe_path(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    이동 조건과 실제 EV / ES 운행 상태를 반영하여
    역 내부 안전 경로를 계산합니다.

    운행 불가 시설이 발견되면 해당 edge를 차단하고
    자동으로 BFS를 다시 수행합니다.
    """

    movement = payload.get(
        "movement"
    )

    mobility_constraints = payload.get(
        "mobility_constraints",
        {},
    )

    if not isinstance(
        movement,
        dict,
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "movement는 객체(dict) 형태여야 합니다."
            ),
        )

    if not isinstance(
        mobility_constraints,
        dict,
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "mobility_constraints는 "
                "객체(dict) 형태여야 합니다."
            ),
        )

    try:
        result = (
            find_realtime_safe_internal_path(
                movement=movement,
                mobility_constraints=(
                    mobility_constraints
                ),
            )
        )

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "역 내부 그래프 파일을 "
                f"찾을 수 없습니다: {error}"
            ),
        ) from error

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(
                error
            ),
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "실시간 역 내부 경로 계산 중 "
                f"오류가 발생했습니다: {error}"
            ),
        ) from error

    return result

# ==============================================================================
# 버스 GBIS 식별자 매칭 디버그
# ==============================================================================

@router.post(
    "/debug/bus-identifiers"
)
async def debug_bus_identifiers(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    카카오 BUS step을 이용하여

    - 버스번호 -> GBIS routeId
    - 승차 정류장 -> GBIS stationId

    매칭 결과를 확인합니다.
    """

    step = payload.get("step")

    if not isinstance(step, dict):
        raise HTTPException(
            status_code=400,
            detail="step은 객체(dict) 형태여야 합니다.",
        )

    step_type = str(
        step.get("step_type", "")
    ).upper()

    if step_type != "BUS":
        raise HTTPException(
            status_code=400,
            detail="BUS step만 테스트할 수 있습니다.",
        )

    try:
        result = match_bus_step_identifiers(
            step
        )

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "버스 식별자 매칭 중 "
                f"오류가 발생했습니다: {error}"
            ),
        ) from error

    return result

# ==============================================================================
# 실시간 저상버스 도착정보 디버그
# ==============================================================================

@router.get(
    "/debug/bus-arrival"
)
async def debug_bus_arrival(
    station_id: str,
    route_id: str,
    bus_number: str | None = None,
):
    """
    GBIS stationId와 routeId를 이용해
    해당 노선의 실시간 저상버스 도착정보를 확인합니다.
    """

    result = await get_low_floor_bus_status(
        station_id=station_id,
        route_id=route_id,
        bus_number=bus_number,
    )

    return result
@router.get("/debug/walking-route")
async def debug_walking_route(
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
):
    return await get_walking_route(
        start_x=start_x,
        start_y=start_y,
        end_x=end_x,
        end_y=end_y,
    )