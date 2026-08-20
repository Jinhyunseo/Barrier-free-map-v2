# backend/verify_pangyo_details.py
import json
from pathlib import Path

GRAPH_FILE = Path(__file__).resolve().parent / "app" / "data" / "station_graphs" / "all_stations_graph.json"

def verify_pangyo():
    if not GRAPH_FILE.exists():
        print("❌ all_stations_graph.json 파일이 없습니다. 빌더를 먼저 실행해주세요.")
        return

    with open(GRAPH_FILE, "r", encoding="utf-8") as f:
        graphs = json.load(f)

    pangyo = graphs.get("판교역")
    if not pangyo:
        print("❌ 판교역 그래프 데이터를 찾을 수 없습니다.")
        return

    edges = pangyo.get("edges", [])

    # 이동수단별 분류
    escalators = [e for e in edges if e.get("transport_type") == "ESCALATOR"]
    stairs = [e for e in edges if e.get("transport_type") == "STAIR"]

    # 단방향 / 양방향 분류
    up_es = [e for e in escalators if e.get("direction") == "UP" and not e.get("is_bidirectional")]
    down_es = [e for e in escalators if e.get("direction") == "DOWN" and not e.get("is_bidirectional")]
    bi_es = [e for e in escalators if e.get("is_bidirectional")]

    print("==================================================")
    print(" 📊 판교역 에스컬레이터 & 계단 상세 데이터 리포트")
    print("==================================================")
    print(f"▶ 총 에스컬레이터 간선: {len(escalators)}개")
    print(f"  - 🔺 단방향 상행 (UP): {len(up_es)}개")
    print(f"  - 🔻 단방향 하행 (DOWN): {len(down_es)}개")
    print(f"  - 🔄 양방향/가변: {len(bi_es)}개")
    print(f"▶ 총 계단 간선: {len(stairs)}개")
    print("==================================================\n")

    print("📍 [1] 단방향 상행(UP) 에스컬레이터 목록:")
    for idx, e in enumerate(up_es, 1):
        print(f"  {idx:02d}. [{e.get('line_name', '공통')}] {e.get('from_floor')} ➔ {e.get('to_floor')} | {e.get('detail_location')}")

    print("\n📍 [2] 단방향 하행(DOWN) 에스컬레이터 목록:")
    for idx, e in enumerate(down_es, 1):
        print(f"  {idx:02d}. [{e.get('line_name', '공통')}] {e.get('from_floor')} ➔ {e.get('to_floor')} | {e.get('detail_location')}")

    if bi_es:
        print("\n📍 [3] 양방향/가변 에스컬레이터 목록:")
        for idx, e in enumerate(bi_es, 1):
            print(f"  {idx:02d}. [{e.get('line_name', '공통')}] {e.get('from_floor')} ↔ {e.get('to_floor')} | {e.get('detail_location')}")

    print("\n📍 [4] 계단(STAIR) 목록:")
    if not stairs:
        print("  (생성된 계단 간선 없음)")
    else:
        for idx, e in enumerate(stairs, 1):
            print(f"  {idx:02d}. [{e.get('line_name', '공통')}] {e.get('from_floor')} ↔ {e.get('to_floor')} | {e.get('detail_location')}")

    print("==================================================")

if __name__ == "__main__":
    verify_pangyo()