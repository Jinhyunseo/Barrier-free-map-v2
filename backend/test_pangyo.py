# backend/test_pangyo.py
from app.services.station_path_service import find_shortest_internal_path

STATION_NAME = "판교역"

def print_result(title: str, result: dict):
    print(f"\n==================================================")
    print(f" {title}")
    print(f"==================================================")
    status = result.get("status")
    print("STATUS:", status)
    
    if status == "SUCCESS":
        print("PATH:")
        for idx, edge in enumerate(result.get("edge_path", []), 1):
            transport = edge.get("transport_type", "WALKING")
            edge_id = edge.get("id", "")
            detail = edge.get("detail_location", "")
            from_n = edge.get("from_node", "")
            to_n = edge.get("to_node", "")
            print(f"  {idx:02d}. [{transport}] {from_n} -> {to_n} | ({detail})")
    else:
        print("  ❌ 경로 탐색 실패:", result.get("message"))


def run_tests():
    # ----------------------------------------------------
    # 시나리오 1: 신분당선 1번 출구 -> 신분당선 B3 강남방면 승강장
    # ----------------------------------------------------
    # 1-1. 일반인 모드 (에스컬레이터 이용)
    r1_gen = find_shortest_internal_path(
        STATION_NAME,
        "PGY_1F_EXIT_1",
        "PGY_신분당선_B3_PLATFORM_GANGNAM",
        mobility_constraints={"avoid_stairs": False, "avoid_escalator": False, "require_elevator": False}
    )
    print_result("TEST 1-1. [신분당선] 1번 출구 -> 강남방면 승강장 (일반인)", r1_gen)

    # 1-2. 휠체어 모드 (엘리베이터 전용)
    r1_wheelchair = find_shortest_internal_path(
        STATION_NAME,
        "PGY_1F_EV_ACCESS_1",
        "PGY_신분당선_B3_PLATFORM_GANGNAM",
        mobility_constraints={"avoid_stairs": True, "avoid_escalator": True, "require_elevator": True}
    )
    print_result("TEST 1-2. [신분당선] 1번 출구 EV접근점 -> 강남방면 승강장 (휠체어)", r1_wheelchair)

    # ----------------------------------------------------
    # 시나리오 2: 신분당선 B3 승강장 -> 경강선 B4 승강장 (환승)
    # ----------------------------------------------------
    # 2-1. 일반인 환승
    r2_gen = find_shortest_internal_path(
        STATION_NAME,
        "PGY_신분당선_B3_PLATFORM_GWANGGYO",
        "PGY_경강선_B4_PLATFORM_YEOJU",
        mobility_constraints={"avoid_stairs": False, "avoid_escalator": False, "require_elevator": False}
    )
    print_result("TEST 2-1. [환승] 신분당선 광교방면 -> 경강선 여주방면 (일반인)", r2_gen)

    # 2-2. 휠체어 환승
    r2_wheelchair = find_shortest_internal_path(
        STATION_NAME,
        "PGY_신분당선_B3_PLATFORM_GWANGGYO",
        "PGY_경강선_B4_PLATFORM_YEOJU",
        mobility_constraints={"avoid_stairs": True, "avoid_escalator": True, "require_elevator": True}
    )
    print_result("TEST 2-2. [환승] 신분당선 광교방면 -> 경강선 여주방면 (휠체어)", r2_wheelchair)

if __name__ == "__main__":
    run_tests()