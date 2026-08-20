from __future__ import annotations

from typing import Any

from app.services.facility_status_service import (
    build_device_status,
    find_device_by_no,
    get_station_facility_data,
)


def _normalize_facility_ids(
    facility_ids: list[str],
) -> list[str]:
    """
    facility_id 목록을 문자열로 정리하고 중복을 제거한다.

    주의:
    실제 번호 정규화는 기존 find_device_by_no()가 담당하므로
    여기서는 원본 facility_id 값을 최대한 유지한다.
    """

    result: list[str] = []
    seen: set[str] = set()

    for facility_id in facility_ids:

        if facility_id is None:
            continue

        value = str(facility_id).strip()

        if not value:
            continue

        if value in seen:
            continue

        seen.add(value)
        result.append(value)

    return result


def _make_unknown_status(
    facility_id: str,
    *,
    mapping_status: str,
    data_source: str = "UNKNOWN",
    updated_at: Any = None,
    message: str = "",
) -> dict[str, Any]:
    """
    조회 실패 / 장비 미매칭 시 사용할 UNKNOWN 결과.
    """

    return {
        "facility_id": facility_id,
        "realtime_status": "UNKNOWN",
        "mapping_status": mapping_status,
        "match_method": "FACILITY_ID_DIRECT",
        "device_no": None,
        "raw_status": None,
        "data_source": data_source,
        "updated_at": updated_at,
        "message": message,
    }


def get_facility_status_summary(
    station_name: str,
    facility_ids: list[str],
) -> dict[str, Any]:
    """
    신형 역사 그래프의 elevator facility_id를 기준으로
    기존 실시간 승강기 데이터와 직접 매칭한다.

    신형 그래프:

        ELEVATOR edge
            ↓
        facility_id
            ↓
        API/JSON elevatorNo(device_no)
            ↓
        find_device_by_no()
            ↓
        AVAILABLE / UNAVAILABLE / UNKNOWN

    정책:

    AVAILABLE
        정상 운행 중.
        경로 탐색에서 차단하지 않는다.

    UNAVAILABLE
        고장 / 점검 / 운행정지 등.
        blocked_facility_ids에 포함한다.

    UNKNOWN
        API 실패, 데이터 없음, 장비번호 미매칭 등.
        안전하게 UNKNOWN으로만 기록하고 차단하지 않는다.

    facility_status_service.py는 수정하지 않고
    기존 검증된 함수만 재사용한다.
    """

    station_name = str(
        station_name or ""
    ).strip()

    normalized_ids = (
        _normalize_facility_ids(
            facility_ids
        )
    )

    # ==================================================
    # 1. 조회 대상 승강기가 없는 경우
    # ==================================================

    if not normalized_ids:

        return {
            "station_name": station_name,
            "status": "SUCCESS",
            "checked_facility_ids": [],
            "available_facility_ids": [],
            "blocked_facility_ids": [],
            "unknown_facility_ids": [],
            "facility_statuses": [],
            "data_source": None,
            "updated_at": None,
        }

    # ==================================================
    # 2. 역 이름이 없는 경우
    # ==================================================

    if not station_name:

        statuses = [
            _make_unknown_status(
                facility_id,
                mapping_status="INVALID_STATION",
                message="station_name이 없습니다.",
            )
            for facility_id
            in normalized_ids
        ]

        return {
            "station_name": station_name,
            "status": "UNKNOWN",
            "checked_facility_ids": normalized_ids,
            "available_facility_ids": [],
            "blocked_facility_ids": [],
            "unknown_facility_ids": normalized_ids,
            "facility_statuses": statuses,
            "data_source": None,
            "updated_at": None,
        }

    # ==================================================
    # 3. 해당 역의 승강기 정보 한 번만 조회
    #
    # 기존 facility_status_service 정책:
    #
    # JSON 존재 → JSON 사용
    # JSON 없음 → API fallback
    # ==================================================

    station_result = (
        get_station_facility_data(
            station_name
        )
    )

    station_status = (
        station_result.get(
            "status"
        )
    )

    data_source = (
        station_result.get(
            "source",
            "UNKNOWN",
        )
    )

    updated_at = (
        station_result.get(
            "updated_at"
        )
    )

    # ==================================================
    # 4. 역 데이터 자체를 가져오지 못한 경우
    #
    # 조회 실패를 "고장"으로 판단하면 안 된다.
    # 전부 UNKNOWN으로 처리한다.
    # ==================================================

    if station_status != "SUCCESS":

        message = str(
            station_result.get(
                "message",
                "승강기 운행 정보를 불러오지 못했습니다.",
            )
        )

        statuses = [
            _make_unknown_status(
                facility_id,
                mapping_status="DATA_NOT_AVAILABLE",
                data_source=data_source,
                updated_at=updated_at,
                message=message,
            )
            for facility_id
            in normalized_ids
        ]

        return {
            "station_name": station_name,
            "status": "UNKNOWN",
            "checked_facility_ids": normalized_ids,
            "available_facility_ids": [],
            "blocked_facility_ids": [],
            "unknown_facility_ids": normalized_ids,
            "facility_statuses": statuses,
            "data_source": data_source,
            "updated_at": updated_at,
        }

    station_devices = (
        station_result.get(
            "items",
            [],
        )
    )

    if not isinstance(
        station_devices,
        list,
    ):
        station_devices = []

    # ==================================================
    # 5. facility_id ↔ elevatorNo 직접 매칭
    # ==================================================

    available_facility_ids: list[str] = []
    blocked_facility_ids: list[str] = []
    unknown_facility_ids: list[str] = []

    facility_statuses: list[
        dict[str, Any]
    ] = []

    for facility_id in normalized_ids:

        # 기존 함수가 내부에서 normalize_device_no()를
        # 양쪽에 적용하여 정확하게 비교한다.
        device = (
            find_device_by_no(
                station_devices,
                facility_id,
            )
        )

        # --------------------------------------------------
        # 장비번호 미매칭
        # --------------------------------------------------

        if device is None:

            unknown_facility_ids.append(
                facility_id
            )

            facility_statuses.append(
                _make_unknown_status(
                    facility_id,
                    mapping_status=(
                        "DEVICE_NOT_FOUND"
                    ),
                    data_source=(
                        data_source
                    ),
                    updated_at=(
                        updated_at
                    ),
                    message=(
                        "facility_id와 일치하는 "
                        "실시간 elevatorNo를 찾지 못했습니다."
                    ),
                )
            )

            continue

        # --------------------------------------------------
        # 기존 status 생성 로직 재사용
        #
        # 내부에서 normalize_operation_status()가 사용됨.
        # --------------------------------------------------

        facility = {
            "facility_id": facility_id,
            "facility_type": "ELEVATOR",
        }

        realtime_info = (
            build_device_status(
                device=device,
                facility=facility,
                match_method=(
                    "FACILITY_ID_DIRECT"
                ),
                mapping_status=(
                    "CONFIRMED"
                ),
                data_source=(
                    data_source
                ),
                updated_at=(
                    updated_at
                ),
            )
        )

        realtime_info = dict(
            realtime_info
        )

        realtime_info[
            "facility_id"
        ] = facility_id

        realtime_status = str(
            realtime_info.get(
                "realtime_status",
                "UNKNOWN",
            )
        ).upper()

        # --------------------------------------------------
        # 혹시 동일 번호인데 시설 종류가 ELEVATOR가 아닌
        # 비정상 데이터라면 차단하지 않고 UNKNOWN 처리
        # --------------------------------------------------

        facility_type_matched = (
            realtime_info.get(
                "facility_type_matched",
                True,
            )
        )

        if not facility_type_matched:

            realtime_info[
                "realtime_status"
            ] = "UNKNOWN"

            realtime_info[
                "mapping_status"
            ] = "FACILITY_TYPE_MISMATCH"

            realtime_info[
                "message"
            ] = (
                "장비번호는 일치하지만 "
                "시설 종류가 ELEVATOR와 일치하지 않습니다."
            )

            unknown_facility_ids.append(
                facility_id
            )

            facility_statuses.append(
                realtime_info
            )

            continue

        # --------------------------------------------------
        # 상태별 분류
        # --------------------------------------------------

        if realtime_status == "AVAILABLE":

            available_facility_ids.append(
                facility_id
            )

        elif realtime_status == "UNAVAILABLE":

            # 실제 이용 불가로 판정된 경우에만 차단한다.
            blocked_facility_ids.append(
                facility_id
            )

        else:

            # 조회 실패/알 수 없는 상태는 차단하지 않는다.
            unknown_facility_ids.append(
                facility_id
            )

        facility_statuses.append(
            realtime_info
        )

    # ==================================================
    # 6. 전체 조회 결과 상태
    # ==================================================

    if blocked_facility_ids:

        overall_status = "UNAVAILABLE"

    elif unknown_facility_ids:

        overall_status = "UNKNOWN"

    else:

        overall_status = "AVAILABLE"

    # ==================================================
    # 7. 최종 반환
    # ==================================================

    return {
        "station_name": station_name,
        "status": overall_status,

        # realtime_route_service에서 사용할 핵심 필드
        "checked_facility_ids": normalized_ids,
        "blocked_facility_ids": blocked_facility_ids,
        "unknown_facility_ids": unknown_facility_ids,

        # 디버깅 / API 응답용 추가 정보
        "available_facility_ids": (
            available_facility_ids
        ),

        "facility_statuses": (
            facility_statuses
        ),

        "data_source": (
            data_source
        ),

        "updated_at": (
            updated_at
        ),
    }