# backend/debug_seongnam.py
import json

try:
    with open("app/data/station_graphs/all_stations_graph.json", encoding="utf-8") as f:
        graph_data = json.load(f)
except Exception as e:
    print("❌ JSON 파일 읽기 실패:", e)
    exit()

seongnam = graph_data.get("성남역", {})

# 노드 데이터 파싱 (리스트/딕셔너리 구조 모두 대응)
raw_nodes = seongnam.get("nodes", [])
if isinstance(raw_nodes, dict):
    node_ids = list(raw_nodes.keys())
elif isinstance(raw_nodes, list):
    node_ids = [n.get("id", str(n)) if isinstance(n, dict) else str(n) for n in raw_nodes]
else:
    node_ids = []

edges = seongnam.get("edges", [])

print("\n==================================================")
print(" 1. 성남역 노드 목록 (EV / EXIT 관련)")
print("==================================================")
for n in node_ids:
    if "EV" in n or "EXIT" in n:
        print(f" - {n}")

print("\n==================================================")
print(" 2. 성남역 생성된 ELEVATOR 간선(Edges) 전체")
print("==================================================")
ev_edges = [e for e in edges if e.get("transport_type") == "ELEVATOR"]
if not ev_edges:
    print(" ❌ 엘리베이터 간선이 0개입니다.")
else:
    for idx, e in enumerate(ev_edges, 1):
        from_n = e.get("from_node", "")
        to_n = e.get("to_node", "")
        detail = e.get("detail_location", "")
        print(f" {idx:02d}. {from_n}  -->  {to_n} | ({detail})")

print("\n==================================================")
print(" 3. SNM_1F_EV_ACCESS_3 (3번 EV) 연결 간선 점검")
print("==================================================")
acc3_edges = [
    e for e in edges 
    if "EV_ACCESS_3" in str(e.get("from_node")) or "EV_ACCESS_3" in str(e.get("to_node"))
]
if not acc3_edges:
    print(" ❌ [문제 원인] SNM_1F_EV_ACCESS_3 에 연결된 간선이 0개입니다!")
    print("    -> 3번 출구 지상 EV 키워드가 맞지 않아 B2 대합실로 들어가는 길이 끊겨 있습니다.")
else:
    for e in acc3_edges:
        from_n = e.get("from_node", "")
        to_n = e.get("to_node", "")
        detail = e.get("detail_location", "")
        print(f"  [연결 성공] {from_n} --> {to_n} | ({detail})")