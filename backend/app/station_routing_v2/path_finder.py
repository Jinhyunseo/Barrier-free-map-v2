from __future__ import annotations

from typing import Iterable, Optional

import networkx as nx


class PathNotFoundError(Exception):
    """
    이용 가능한 역사 내부 경로를 찾지 못했을 때 사용한다.
    """
    pass


# ==============================================================================
# 💡 이동 수단 표시용 라벨 (JSON 데이터가 아니라 코드 상수로 관리)
# ==============================================================================

MODE_LABELS: dict[str, str] = {
    "WALK": "도보",
    "ELEVATOR": "엘리베이터",
    "ESCALATOR": "에스컬레이터",
    "STAIRS": "계단",
}


def _get_mode_label(mode: str | None) -> str:
    if not mode:
        return "이동"
    return MODE_LABELS.get(str(mode).upper(), str(mode))


def apply_confirmed_edges_only(
    graph: nx.DiGraph,
) -> nx.DiGraph:
    """
    공식적으로 확인된(CONFIRMED) edge만 남긴
    새로운 그래프를 반환한다.

    INFERRED / UNKNOWN / confidence 누락 edge는
    실제 경로 탐색에 사용하지 않는다.

    원본 graph는 수정하지 않는다.
    """

    safe_graph = graph.copy()

    edges_to_remove = []

    for source, target, data in safe_graph.edges(data=True):
        if data.get("confidence") != "CONFIRMED":
            edges_to_remove.append((source, target))

    safe_graph.remove_edges_from(edges_to_remove)

    return safe_graph


def apply_blocked_facilities(
    graph: nx.DiGraph,
    blocked_facility_ids: Optional[Iterable[str]] = None,
) -> nx.DiGraph:
    """
    고장/점검 중인 엘리베이터 facility_id를 받아
    해당 ELEVATOR edge를 제거한 새로운 그래프를 반환한다.

    원본 graph는 수정하지 않는다.

    예:
        blocked_facility_ids = ["2050606"]

    → facility_id가 2050606인 ELEVATOR edge를
      정방향/역방향 모두 제거한다.
    """

    safe_graph = graph.copy()

    blocked_ids = {
        str(facility_id)
        for facility_id in (blocked_facility_ids or [])
        if facility_id is not None
    }

    if not blocked_ids:
        return safe_graph

    edges_to_remove = []

    for source, target, data in safe_graph.edges(data=True):
        if data.get("mode") != "ELEVATOR":
            continue

        facility_id = data.get("facility_id")

        if facility_id is not None and str(facility_id) in blocked_ids:
            edges_to_remove.append((source, target))

    safe_graph.remove_edges_from(edges_to_remove)

    return safe_graph


def build_safe_graph(
    graph: nx.DiGraph,
    blocked_facility_ids: Optional[Iterable[str]] = None,
) -> nx.DiGraph:
    """
    실제 경로 탐색에 사용할 안전한 그래프를 생성한다.

    처리 순서:
        1. CONFIRMED edge만 유지
        2. 고장/점검 중인 ELEVATOR edge 제거

    원본 graph는 수정하지 않는다.
    """

    safe_graph = apply_confirmed_edges_only(graph)

    safe_graph = apply_blocked_facilities(
        safe_graph,
        blocked_facility_ids,
    )

    return safe_graph


def validate_path_nodes(
    graph: nx.DiGraph,
    start_node: str,
    end_node: str,
) -> None:
    """
    출발/도착 node가 그래프에 실제로 존재하는지 확인한다.
    """

    if start_node not in graph:
        raise ValueError(
            f"출발 node가 그래프에 존재하지 않습니다: {start_node}"
        )

    if end_node not in graph:
        raise ValueError(
            f"도착 node가 그래프에 존재하지 않습니다: {end_node}"
        )


def find_internal_path(
    graph: nx.DiGraph,
    start_node: str,
    end_node: str,
    blocked_facility_ids: Optional[Iterable[str]] = None,
) -> list[str]:
    """
    역사 내부 경로를 탐색한다.

    현재 MVP에서는 시간/거리 가중치를 사용하지 않으므로
    NetworkX shortest_path의 기본 hop 수 기준으로 탐색한다.

    처리 순서:
        1. start/end node 존재 여부 확인
        2. CONFIRMED edge만 유지
        3. 고장난 EV edge 제거
        4. 이용 가능한 경로 탐색
        5. 없으면 PathNotFoundError 발생
    """

    validate_path_nodes(
        graph,
        start_node,
        end_node,
    )

    safe_graph = build_safe_graph(
        graph,
        blocked_facility_ids,
    )

    try:
        return nx.shortest_path(
            safe_graph,
            source=start_node,
            target=end_node,
        )

    except nx.NetworkXNoPath as exc:
        raise PathNotFoundError(
            f"이용 가능한 역사 내부 경로가 없습니다: "
            f"{start_node} -> {end_node}"
        ) from exc


def get_path_edges(
    graph: nx.DiGraph,
    node_path: list[str],
) -> list[dict]:
    """
    node 경로를 실제 edge 정보 배열로 변환한다.

    💡 [수정] source_file(로컬 절대경로, 그래프 병합 디버깅용 메타데이터)은
    사용자 응답으로 나가면 안 되는 값이라 여기서 걸러낸다. get_path_steps()도
    이 함수의 결과를 그대로 쓰기 때문에, 여기 한 곳만 고치면 edge_path와
    steps 양쪽 다 자동으로 깨끗해진다.
    """

    if len(node_path) < 2:
        return []

    result = []

    for index in range(len(node_path) - 1):
        source = node_path[index]
        target = node_path[index + 1]

        if not graph.has_edge(source, target):
            raise ValueError(
                f"node_path에 존재하지만 실제 graph edge가 없습니다: "
                f"{source} -> {target}"
            )

        edge_data = graph.get_edge_data(
            source,
            target,
        ).copy()

        # 내부 디버깅/병합용 메타데이터는 API 응답에서 제외한다.
        edge_data.pop("source_file", None)

        result.append(
            {
                "source": source,
                "target": target,
                **edge_data,
            }
        )

    return result


def _describe_node(graph: nx.DiGraph, node_id: str) -> dict:
    """
    node 하나에 대한 표시용 정보(이름/층)를 안전하게 만든다.

    name/floor가 그래프 JSON에 없는 경우, 빈 문자열이나 None을 그대로
    프론트에 내려보내는 대신 node_id 자체를 이름 fallback으로 사용해서
    최소한 "뭔가 표시는 되게" 만든다. floor는 없으면 None을 유지한다
    (없는 층을 지어내는 것보다, 프론트에서 층 표시 자체를 생략하는 게 낫다).
    """

    node_data = graph.nodes.get(node_id, {})

    name = node_data.get("name") or node_id
    floor = node_data.get("floor")

    return {"name": name, "floor": floor}


def _build_floor_text(source_floor: str | None, target_floor: str | None) -> str | None:
    if not source_floor and not target_floor:
        return None
    if not source_floor or not target_floor:
        return source_floor or target_floor
    if source_floor == target_floor:
        return source_floor
    return f"{source_floor} → {target_floor}"


def get_path_steps(
    graph: nx.DiGraph,
    node_path: list[str],
) -> list[dict]:
    """
    역사 내부 경로의 단계별 이동 정보를 생성한다.

    - 기존 필드는 유지한다.
    - source/target 위치와 층 정보를 함께 제공한다.
    - auto_reverse=True인 edge는 원래 정방향 instruction을
      그대로 사용하지 않고 실제 이동 방향 기준으로 안내문을 재생성한다.
    """

    edge_path = get_path_edges(
        graph,
        node_path,
    )

    steps = []

    for index, edge in enumerate(
        edge_path,
        start=1,
    ):
        source_id = edge["source"]
        target_id = edge["target"]

        source_node = graph.nodes[source_id]
        target_node = graph.nodes[target_id]

        # ------------------------------------------------------
        # 노드 정보
        # ------------------------------------------------------

        source_name = (
            source_node.get("name")
            or source_id
        )

        target_name = (
            target_node.get("name")
            or target_id
        )

        source_floor = source_node.get(
            "floor"
        )

        target_floor = target_node.get(
            "floor"
        )

        # ------------------------------------------------------
        # 이동 방식
        # ------------------------------------------------------

        mode = str(
            edge.get("mode")
            or "WALK"
        ).upper()

        mode_label = _get_mode_label(
            mode
        )

        # ------------------------------------------------------
        # 층 이동 문자열
        # ------------------------------------------------------

        floor_text = (
            _build_floor_text(
                source_floor,
                target_floor,
            )
        )

        # ------------------------------------------------------
        # 원본 instruction
        # ------------------------------------------------------

        original_instruction = (
            edge.get("instruction")
        )

        auto_reverse = bool(
            edge.get(
                "auto_reverse",
                False,
            )
        )

        # ------------------------------------------------------
        # 실제 사용자 표시용 instruction 생성
        #
        # auto_reverse인 경우 기존 instruction은
        # 정방향 기준 문장이므로 다시 만든다.
        # ------------------------------------------------------

        if auto_reverse:

            # --------------------------------------------------
            # 엘리베이터
            # --------------------------------------------------

            if mode == "ELEVATOR":

                if (
                    source_floor
                    and target_floor
                    and source_floor != target_floor
                ):
                    display_instruction = (
                        f"엘리베이터를 이용해 "
                        f"{source_floor}에서 "
                        f"{target_floor}로 이동"
                    )

                else:
                    display_instruction = (
                        f"{source_name}에서 "
                        f"{target_name}으로 "
                        f"엘리베이터를 이용해 이동"
                    )

            # --------------------------------------------------
            # 에스컬레이터
            # --------------------------------------------------

            elif mode == "ESCALATOR":

                if (
                    source_floor
                    and target_floor
                    and source_floor != target_floor
                ):
                    display_instruction = (
                        f"에스컬레이터를 이용해 "
                        f"{source_floor}에서 "
                        f"{target_floor}로 이동"
                    )

                else:
                    display_instruction = (
                        f"{source_name}에서 "
                        f"{target_name}으로 이동"
                    )

            # --------------------------------------------------
            # 계단
            # --------------------------------------------------

            elif mode == "STAIRS":

                if (
                    source_floor
                    and target_floor
                    and source_floor != target_floor
                ):
                    display_instruction = (
                        f"계단을 이용해 "
                        f"{source_floor}에서 "
                        f"{target_floor}로 이동"
                    )

                else:
                    display_instruction = (
                        f"{source_name}에서 "
                        f"{target_name}으로 이동"
                    )

            # --------------------------------------------------
            # WALK
            # --------------------------------------------------

            else:
                display_instruction = (
                    f"{source_name}에서 "
                    f"{target_name}으로 이동"
                )

        # ------------------------------------------------------
        # 정방향 edge는 기존 그래프 instruction 유지
        # ------------------------------------------------------

        else:

            if original_instruction:
                display_instruction = str(
                    original_instruction
                )

            elif mode == "ELEVATOR":
                if (
                    source_floor
                    and target_floor
                    and source_floor != target_floor
                ):
                    display_instruction = (
                        f"엘리베이터를 이용해 "
                        f"{source_floor}에서 "
                        f"{target_floor}로 이동"
                    )
                else:
                    display_instruction = (
                        f"{source_name}에서 "
                        f"{target_name}으로 이동"
                    )

            else:
                display_instruction = (
                    f"{source_name}에서 "
                    f"{target_name}으로 이동"
                )

        # ------------------------------------------------------
        # step 생성
        # ------------------------------------------------------

        steps.append(
            {
                # 기존 필드
                "step": index,
                "source": source_id,
                "target": target_id,
                "target_name": target_name,
                "floor": target_floor,
                "mode": mode,
                "facility_id": edge.get(
                    "facility_id"
                ),

                # 중요:
                # 프론트가 기존 instruction을 그대로 사용하므로
                # 실제 표시용 문장으로 교체한다.
                "instruction": display_instruction,

                # 신규 상세 필드
                "source_name": source_name,
                "source_floor": source_floor,
                "target_floor": target_floor,
                "mode_label": mode_label,
                "floor_text": floor_text,

                # 디버깅용
                "auto_reverse": auto_reverse,
            }
        )

    return steps

def find_internal_route(
    graph: nx.DiGraph,
    start_node: str,
    end_node: str,
    blocked_facility_ids: Optional[Iterable[str]] = None,
) -> dict:
    """
    서비스에서 가장 편하게 사용할 메인 함수.

    성공 시:
    {
        "status": "SUCCESS",
        "start_node": ...,
        "end_node": ...,
        "node_path": [...],
        "edge_path": [...],
        "steps": [...]
    }

    경로가 없으면:
    {
        "status": "PATH_NOT_FOUND",
        ...
    }
    """

    try:
        node_path = find_internal_path(
            graph=graph,
            start_node=start_node,
            end_node=end_node,
            blocked_facility_ids=blocked_facility_ids,
        )

    except PathNotFoundError:
        return {
            "status": "PATH_NOT_FOUND",
            "start_node": start_node,
            "end_node": end_node,
            "node_path": [],
            "edge_path": [],
            "steps": [],
        }

    # find_internal_path와 동일한 안전 조건이 적용된
    # 그래프에서 edge/step 정보를 생성한다.
    safe_graph = build_safe_graph(
        graph,
        blocked_facility_ids,
    )

    edge_path = get_path_edges(
        safe_graph,
        node_path,
    )

    steps = get_path_steps(
        safe_graph,
        node_path,
    )

    return {
        "status": "SUCCESS",
        "start_node": start_node,
        "end_node": end_node,
        "node_path": node_path,
        "edge_path": edge_path,
        "steps": steps,
    }
