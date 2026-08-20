# main.py
from map_data import sample_map
from router import find_optimal_route
from gemini_explain import generate_route_reason

if __name__ == "__main__":
    # 1. UI에서 사용자가 입력한 값 가정 (테스트용)
    # main.py 예시

    user_constraints = {
    "no_stairs": True,               # 계단 이용 어려움
    "need_elevator": True,           # 엘리베이터 필수
    "no_escalator": False,          # 에스컬레이터 이용 어려움
    "avoid_slope": True,             # 급경사 피하기
    "require_low_floor_bus": True    # 저상 버스 필요 (신규 추가!)
}

    selected_condition_names = ["계단 이용 어려움", "엘리베이터 필수", "급경사 피하기", "저상 버스 필요"]
    user_preference = "최소 도보"

    # 2. Hard Constraint + Preference 기반 경로 탐색
    result = find_optimal_route(sample_map, 'A_출발지', 'F_도착지', user_constraints, user_preference)

    # 3. 결과 출력 및 AI 설명 생성
    if result:
        print("=== 1. 경로 탐색 성공 ===")
        print(f"추천 경로: {' ➔ '.join(result['path'])}")
        print(f"소요 시간: {result['total_time_min']}분 | 도보: {result['total_walk_m']}m | 환승: {result['transfers']}회")
        
        print("\n=== 2. Gemini AI 추천 이유 생성 중 ===")
        reason = generate_route_reason(selected_condition_names, user_preference, result)
        print(f"[추천 이유]: {reason}")
    else:
        print("선택하신 조건에 들어맞는 안전한 경로가 없습니다.")