from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import networkx as nx


class GraphMergeError(Exception):
    """
    노선별 그래프 + 환승간선 그래프 json을 하나의 역 그래프로 병합하는
    과정에서 발생한 오류.
    """

    pass


@dataclass(frozen=True)
class StationSegment:
    """
    역 그래프 json 파일 하나를 표현한다.

    환승역은 노선별 세그먼트(예: 8호선, 수인분당선)와
    환승간선 세그먼트(TRANSFER_TRUNK)로 나뉘어 여러 개의 StationSegment로 존재하고,
    환승역이 아닌 역은 단일 StationSegment로 존재한다.
    """

    path: Path
    data: dict

    @property
    def station_code(self) -> str:
        return self.data["station_code"]

    @property
    def parent_station_code(self) -> str:
        # parent_station_code가 없으면 물리적으로 분리되지 않은 단일 역으로 취급한다.
        return self.data.get("parent_station_code", self.data["station_code"])

    @property
    def nodes(self) -> list[dict]:
        return self.data.get("nodes", [])

    @property
    def edges(self) -> list[dict]:
        return self.data.get("edges", [])

    @property
    def interfaces(self) -> list[dict]:
        return self.data.get("interfaces", [])


def load_segment(path: str | Path) -> StationSegment:
    path = Path(path)
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return StationSegment(path=path, data=data)


def load_segments(paths: Iterable[str | Path]) -> list[StationSegment]:
    return [load_segment(path) for path in paths]


def _is_transfer_trunk_segment(data: dict) -> bool:
    return data.get("line") == "TRANSFER_TRUNK" or data.get("segment") == "TRANSFER_TRUNK"


def find_station_segment_files(
    data_dir: str | Path,
    parent_station_code: str,
    *,
    include_transfer_trunk: bool = True,
) -> list[Path]:
    """
    data_dir 아래의 모든 *.json 파일 중 parent_station_code가 일치하는
    파일 경로를 찾는다.

    환승역: 노선별 그래프 파일들과 환승간선 그래프 파일이 모두 매칭되어 함께 반환된다.
    비환승역: 해당 역의 단일 그래프 파일만 매칭되어 반환된다.

    즉 이 함수 하나로 환승역/비환승역 구분 없이 특정 역(parent_station_code)에
    필요한 모든 세그먼트 파일을 동일한 방식으로 찾을 수 있다.

    include_transfer_trunk=False로 호출하면 환승간선(TRANSFER_TRUNK) 세그먼트
    파일은 제외하고 노선별 파일만 반환한다.
    """

    data_dir = Path(data_dir)
    matches = []

    for path in sorted(data_dir.rglob("*.json")):
        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        if data.get("parent_station_code") != parent_station_code:
            continue

        if not include_transfer_trunk and _is_transfer_trunk_segment(data):
            continue

        matches.append(path)

    return matches


# 같은 노드 id가 여러 파일에 non-external로 정의되어 있을 때, 이 필드들은
# 반드시 일치해야 "물리적으로 같은 노드"로 보고 하나로 합칠 수 있다.
# (예: 층이나 종류가 다르면 우연히 id만 겹친 별개의 노드일 가능성이 높다)
_NODE_IDENTITY_FIELDS = ("type", "floor")


def _merge_duplicate_node_definitions(
    node_id: str,
    defs: list[tuple[StationSegment, dict]],
) -> dict:
    """
    같은 노드 id가 여러(환승 대상) 세그먼트 파일에 각각 non-external로
    정의되어 있는 경우를 처리한다.

    트렁크(환승간선) 파일 없이 두 노선 파일이 같은 물리적 경계 노드
    (예: 두 노선이 함께 쓰는 대합실)를 서로 external 표시 없이 동일한 id로
    각자 정의하는 경우가 있을 수 있다. 이때는 에러를 내는 대신 하나의
    노드로 합쳐서, 그 노드에 연결된 두 노선의 edge가 자연스럽게
    이어지도록 한다.

    파일 경로 기준으로 정렬해 병합 순서와 무관하게 항상 같은 결과를 낸다.
    속성이 겹치는 필드는 정렬상 가장 앞선 파일의 값을 사용한다.
    단, type/floor처럼 노드의 정체성을 규정하는 필드가 서로 다르면
    같은 노드로 볼 수 없으므로 충돌로 간주해 에러를 낸다.
    """

    sorted_defs = sorted(defs, key=lambda item: str(item[0].path))
    base_segment, base_node = sorted_defs[0]

    for other_segment, other_node in sorted_defs[1:]:
        for field in _NODE_IDENTITY_FIELDS:
            base_value = base_node.get(field)
            other_value = other_node.get(field)

            if base_value != other_value:
                raise GraphMergeError(
                    f"노드 id '{node_id}'가 서로 다른 파일에서 서로 다른 "
                    f"'{field}' 값으로 정의되어 같은 노드로 병합할 수 없습니다: "
                    f"{base_segment.path.name}={base_value!r} vs "
                    f"{other_segment.path.name}={other_value!r}"
                )

    merged_attrs: dict = {}

    for segment, node in sorted_defs:
        for key, value in node.items():
            if key in ("id", "external", "defined_in"):
                continue

            if key not in merged_attrs:
                merged_attrs[key] = value

    merged_attrs["source_files"] = [str(segment.path) for segment, _ in sorted_defs]

    return merged_attrs


def _merge_nodes(segments: list[StationSegment], graph: nx.DiGraph) -> None:
    internal_defs: dict[str, list[tuple[StationSegment, dict]]] = defaultdict(list)
    external_refs: dict[str, list[tuple[StationSegment, dict]]] = defaultdict(list)

    for segment in segments:
        for node in segment.nodes:
            node_id = node["id"]

            if node.get("external"):
                external_refs[node_id].append((segment, node))
            else:
                internal_defs[node_id].append((segment, node))

    # external=true 노드는 다른 세그먼트 파일에 정의된 노드를 그대로 참조하는
    # 경계 노드다. 그 원본 정의(internal 정의)가 병합 대상에 포함되어 있지 않으면
    # 환승 경로가 끊어지므로, 반드시 함께 병합하도록 강제한다.
    missing_refs = set(external_refs) - set(internal_defs)

    if missing_refs:
        details = []

        for node_id in sorted(missing_refs):
            segment, node = external_refs[node_id][0]
            defined_in = node.get("defined_in", "알 수 없는 파일")
            details.append(
                f"'{node_id}' (참조 파일: {segment.path.name}, 원본 파일: {defined_in})"
            )

        raise GraphMergeError(
            "환승/외부 참조 노드의 원본 정의 파일이 병합 대상에 포함되지 않았습니다. "
            "환승역은 관련된 모든 노선 세그먼트 + 환승간선 세그먼트 파일을 "
            "함께 전달해야 합니다: " + "; ".join(details)
        )

    for node_id, defs in internal_defs.items():
        if len(defs) == 1:
            segment, node = defs[0]
            attrs = {
                key: value
                for key, value in node.items()
                if key not in ("id", "external", "defined_in")
            }
            attrs["source_files"] = [str(segment.path)]
        else:
            attrs = _merge_duplicate_node_definitions(node_id, defs)

        graph.add_node(node_id, **attrs)


def _merge_edges(
    segments: list[StationSegment],
    graph: nx.DiGraph,
) -> None:
    """
    여러 세그먼트의 edge를 하나의 그래프로 병합한다.

    원본 JSON에 정의된 edge는 그대로 우선 등록한다.

    이후 현재 EV-only MVP 정책에 따라:
    - WALK
    - ELEVATOR

    edge는 역방향 edge가 따로 정의되어 있지 않은 경우
    자동으로 역방향도 추가한다.

    이렇게 하면:
    - 단일역 graph_loader.py와 동일하게 WALK/ELEVATOR 양방향 이동 가능
    - 나중에 JSON에 역방향 edge가 명시되어 있으면 그 값을 우선 사용
    - ESCALATOR 등 다른 mode는 임의로 양방향 처리하지 않음
    """

    # ==================================================
    # 1. 원본 JSON에 명시된 edge들을 먼저 모두 등록
    # ==================================================

    edge_owner: dict[tuple[str, str], StationSegment] = {}

    for segment in segments:
        for edge in segment.edges:
            source = edge["source"]
            target = edge["target"]

            # ------------------------------------------
            # source / target 노드 존재 여부 확인
            # ------------------------------------------

            for endpoint in (source, target):
                if endpoint not in graph:
                    raise GraphMergeError(
                        f"{segment.path} 의 edge "
                        f"'{edge.get('id', f'{source}->{target}')}'가 "
                        f"참조하는 노드 '{endpoint}'가 "
                        "병합된 노드 목록에 없습니다."
                    )

            key = (source, target)

            attrs = {
                attr_key: attr_value
                for attr_key, attr_value in edge.items()
                if attr_key not in ("source", "target")
            }

            attrs["source_file"] = str(segment.path)

            # ------------------------------------------
            # 같은 방향 edge가 이미 존재하는 경우
            # ------------------------------------------

            if key in edge_owner:
                existing = graph.edges[key]

                # 완전히 같은 edge라면 중복만 무시
                if existing.get("id") == attrs.get("id"):
                    continue

                raise GraphMergeError(
                    f"'{source}' -> '{target}' 구간에 "
                    "서로 다른 파일에서 정의된 edge가 충돌합니다: "
                    f"{edge_owner[key].path.name}"
                    f"({existing.get('id')}) vs "
                    f"{segment.path.name}"
                    f"({attrs.get('id')})"
                )

            graph.add_edge(
                source,
                target,
                **attrs,
            )

            edge_owner[key] = segment

    # ==================================================
    # 2. WALK / ELEVATOR 역방향 edge 자동 생성
    # ==================================================

    #
    # graph.edges()를 순회하면서 동시에 edge를 추가하면
    # RuntimeError가 발생할 수 있으므로 list로 복사한다.
    #
    current_edges = list(
        graph.edges(data=True)
    )

    for source, target, attrs in current_edges:

        mode = str(
            attrs.get("mode", "")
        ).upper()

        # 현재 EV-only MVP에서
        # 양방향 이동을 허용하는 mode
        if mode not in {
            "WALK",
            "ELEVATOR",
        }:
            continue

        reverse_source = target
        reverse_target = source

        # ------------------------------------------
        # 역방향 edge가 원래 JSON에 이미 있다면
        # 그 정의를 그대로 사용한다.
        # ------------------------------------------

        if graph.has_edge(
            reverse_source,
            reverse_target,
        ):
            continue

        # ------------------------------------------
        # 역방향 edge 생성
        # ------------------------------------------

        reverse_attrs = dict(attrs)

        # 같은 물리적 시설/통로이므로
        # id, facility_id 등 원본 속성을 그대로 유지한다.
        reverse_attrs["auto_reverse"] = True

        graph.add_edge(
            reverse_source,
            reverse_target,
            **reverse_attrs,
        )
def _as_id_list(value: object) -> list[str]:
    """
    interface의 node_id/connects_to_node/connects_to_file 값을 리스트로
    정규화한다. 단일 문자열이면 원소 하나짜리 리스트로, 이미 리스트/튜플이면
    그대로(빈 값 제외) 사용한다. 한 경계 노드가 여러 노드와 연결되는
    다자 환승역(3개 이상 노선이 만나는 역 등)을 표현할 수 있도록 하기 위함이다.
    """

    if value is None:
        return []

    if isinstance(value, str):
        return [value]

    if isinstance(value, (list, tuple)):
        return [item for item in value if item]

    raise GraphMergeError(f"interface 필드 값의 타입을 처리할 수 없습니다: {value!r}")


def _validate_interfaces(
    segments: list[StationSegment],
    graph: nx.DiGraph,
    *,
    validate_connects_to_node: bool = True,
) -> None:
    for segment in segments:
        for interface in segment.interfaces:
            node_ids = _as_id_list(interface.get("node_id"))
            connects_to_nodes = _as_id_list(interface.get("connects_to_node"))

            for node_id in node_ids:
                if node_id not in graph:
                    raise GraphMergeError(
                        f"{segment.path} 의 interface 노드 '{node_id}'가 "
                        "병합된 그래프에 없습니다."
                    )

            if not validate_connects_to_node:
                # 환승간선 세그먼트를 의도적으로 제외한 병합에서는
                # interface가 가리키는 상대 노드(환승간선 쪽)가 그래프에
                # 없는 것이 정상이므로 이 검사를 건너뛴다.
                continue

            for connects_to_node in connects_to_nodes:
                if connects_to_node not in graph:
                    connects_to_files = _as_id_list(interface.get("connects_to_file"))
                    connects_to_file = (
                        ", ".join(connects_to_files)
                        if connects_to_files
                        else "알 수 없는 파일"
                    )
                    raise GraphMergeError(
                        f"{segment.path} 의 interface가 참조하는 노드 "
                        f"'{connects_to_node}'가 병합 대상에 포함되지 않았습니다. "
                        f"'{connects_to_file}' 파일이 함께 전달되었는지 확인하세요."
                    )


def _segments_include_transfer_trunk(segments: list[StationSegment]) -> bool:
    return any(_is_transfer_trunk_segment(segment.data) for segment in segments)


def merge_station_segments(
    segments: list[StationSegment],
    *,
    validate_interfaces: Optional[bool] = None,
) -> nx.DiGraph:
    """
    같은 역(parent_station_code)에 속한 세그먼트들을 하나의 nx.DiGraph로 병합한다.

    전달된 세그먼트만으로 자동으로 두 가지 상황을 모두 처리한다(호출하는
    쪽에서 환승간선 포함 여부를 True/False로 미리 지정할 필요가 없다):

    - 환승간선(TRANSFER_TRUNK) 세그먼트가 포함된 경우: 노선별 세그먼트의
      external=true 경계 노드가 환승간선 세그먼트에 정의된 원본 노드로
      대체되어 이어진다.
    - 환승간선 세그먼트가 없는 경우: 두 노선 세그먼트가 같은 경계 노드 id를
      각자 external 표시 없이 동일하게 정의하고 있다면, 그 노드들을 하나로
      합쳐서 두 노선이 그 노드를 통해 이어지도록 한다(같은 id인데
      type/floor가 다르면 서로 다른 노드로 보고 에러를 낸다).
    - 위 두 연결 수단이 모두 없으면 각 노선의 노드/edge가 한 그래프 안에
      함께 담기기만 하고 서로 이어지지는 않는다.
    - 비환승역: 세그먼트가 하나뿐이므로 사실상 원본 그래프를 그대로 반환한다.

    validate_interfaces가 None(기본값)이면, 전달된 세그먼트 중 환승간선
    세그먼트가 있는지를 보고 자동으로 정한다: 환승간선이 있으면 엄격하게
    검증하고(누락된 연결을 바로 알 수 있도록), 환승간선이 없으면 노선
    파일의 interfaces가 가리키는 상대(환승간선) 노드가 없어도 에러를 내지
    않는다. 필요하면 True/False로 직접 지정해 이 자동 판단을 덮어쓸 수 있다.

    세그먼트 목록의 순서와 무관하게 동일한 결과를 만든다.
    """

    if not segments:
        raise GraphMergeError("병합할 세그먼트가 없습니다.")

    parent_codes = {segment.parent_station_code for segment in segments}

    if len(parent_codes) > 1:
        raise GraphMergeError(
            "서로 다른 parent_station_code를 가진 세그먼트는 함께 병합할 수 없습니다: "
            f"{sorted(parent_codes)}"
        )

    if validate_interfaces is None:
        validate_interfaces = _segments_include_transfer_trunk(segments)

    graph = nx.DiGraph()
    graph.graph["parent_station_code"] = next(iter(parent_codes))
    graph.graph["segments"] = [
        {
            "station_code": segment.station_code,
            "line": segment.data.get("line"),
            "segment": segment.data.get("segment"),
            "source_file": str(segment.path),
        }
        for segment in segments
    ]

    _merge_nodes(segments, graph)
    _merge_edges(segments, graph)
    _validate_interfaces(
        segments,
        graph,
        validate_connects_to_node=validate_interfaces,
    )

    return graph


def build_station_graph(
    paths: Iterable[str | Path],
    *,
    validate_interfaces: Optional[bool] = None,
) -> nx.DiGraph:
    """
    역 그래프 json 파일 경로들을 받아 병합된 하나의 그래프를 만든다.

    환승역이면 노선별 파일 + (있다면) 환승간선 파일 경로를 모두 전달하면 되고,
    환승간선 파일이 없는 역이면 노선별 파일 경로만 전달하면 된다 — 어느 쪽인지
    직접 지정하지 않아도 자동으로 처리된다(자세한 내용은
    merge_station_segments 참고). 비환승역이면 해당 역의 단일 파일 경로만
    전달하면 된다.
    """

    segments = load_segments(paths)
    return merge_station_segments(segments, validate_interfaces=validate_interfaces)


def build_station_graph_from_directory(
    data_dir: str | Path,
    parent_station_code: str,
    *,
    include_transfer_trunk: bool = True,
    validate_interfaces: Optional[bool] = None,
) -> nx.DiGraph:
    """
    data_dir에서 parent_station_code에 해당하는 세그먼트 파일을 찾아
    자동으로 병합한 그래프를 만든다.

    보통은 아무 옵션도 넘기지 않고 호출하면 된다:
    환승간선(TRANSFER_TRUNK) 파일이 있는 역은 그 파일까지 함께 병합해
    노선 간 환승 경로를 탐색할 수 있는 그래프를 만들고, 환승간선 파일이
    없는 역은 노선별 파일만 병합한다(경계 노드를 같은 id로 공유하고
    있다면 그 노드를 통해 자동으로 이어진다). 비환승역은 파일이 하나뿐이므로
    그 파일만 사용한다. 즉 True/False를 미리 정할 필요 없이 이 함수 하나로
    환승역/비환승역, 환승간선 있음/없음을 모두 동일하게 처리한다.

    include_transfer_trunk=False를 명시하면 환승간선 파일이 실제로 있어도
    찾아오지 않고 노선별 파일만 병합한다(디버깅 등으로 환승간선을 의도적으로
    빼고 싶을 때 사용).

    validate_interfaces는 기본적으로 merge_station_segments와 동일하게
    자동으로 정해지며, 필요하면 직접 True/False로 덮어쓸 수 있다.
    """

    paths = find_station_segment_files(
        data_dir,
        parent_station_code,
        include_transfer_trunk=include_transfer_trunk,
    )

    if not paths:
        raise GraphMergeError(
            f"'{parent_station_code}'에 해당하는 그래프 파일을 찾지 못했습니다: {data_dir}"
        )

    return build_station_graph(paths, validate_interfaces=validate_interfaces)
