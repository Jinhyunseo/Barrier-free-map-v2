# backend/test_seongnam.py
import json
import heapq
from pathlib import Path

# 실시간 all_stations_graph.json 직접 로드
GRAPH_FILE = Path(__file__).resolve().parent / "app" / "data" / "station_graphs" / "all_stations_graph.json"

def load_seongnam_graph():
    with open(GRAPH_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("성남역", {})

def dijkstra_find_path(start_node: str, end_node: str, avoid_stairs_and_es: bool = False):
    graph = load_seongnam_graph()
    edges = graph.get("edges", [])
    
    # 인접 리스트 생성
    adj = {}
    for edge in edges:
        u = edge.get("from_node")
        v = edge.get("to_node")
        transport = edge.get("transport_type", "WALKING")
        
        # 휠체어 제약 필터 (계단 및 에스컬레이터 제외)
        if avoid_stairs_and_es and transport in ["STAIR", "ESCALATOR"]:
            continue
            
        if u not in adj: adj[u] = []
        adj[u].append((v, edge))
        
        # 양방향 간선 처리
        if edge.get("is_bidirectional", True):
            if v not in adj: adj[v] = []
            adj[v].append((u, edge))

    # 다익스트라 최단 경로 탐색 (heapq 비교 에러 방지용 count 추가)
    count = 0
    pq = [(0, count, start_node, [])]
    visited = set()
    
    while pq:
        cost, _, current, path = heapq.heappop(pq)
        
        if current == end_node:
            return {"status": "SUCCESS", "edge_path": path}
            
        if current in visited:
            continue
        visited.add(current)
        
        for neighbor, edge in adj.get(current, []):
            if neighbor not in visited:
                count += 1
                heapq.heappush(pq, (cost + 1, count, neighbor, path + [edge]))
                
    return {"status": "PATH_NOT_FOUND", "message": "None"}

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
            detail = edge.get("detail_location", "")
            from_n = edge.get("from_node", "")
            to_n = edge.get("to_node", "")
            print(f"  {idx:02d}. [{transport}] {from_n} -> {to_n} | ({detail})")
    else:
        print("  ❌ 경로 탐색 실패:", result.get("message"))

def run_tests():
    # 1-1. 1번 출구 -> 여주방면 (일반인)
    r1_gen = dijkstra_find_path("SNM_1F_EXIT_1", "SNM_경강선_B3_PLATFORM_YEOJU", avoid_stairs_and_es=False)
    print_result("TEST 1-1. [성남역] 1번 출구 -> 여주방면 승강장 (일반인)", r1_gen)

    # 1-2. 1·4번 EV접근점 -> 여주방면 (휠체어)
    r1_wheelchair = dijkstra_find_path("SNM_1F_EV_ACCESS_1_4", "SNM_경강선_B3_PLATFORM_YEOJU", avoid_stairs_and_es=True)
    print_result("TEST 1-2. [성남역] 1·4번 선큰 지상 EV -> 여주방면 승강장 (휠체어)", r1_wheelchair)

    # 2-1. 3번 출구 -> 판교방면 (일반인)
    r2_gen = dijkstra_find_path("SNM_1F_EXIT_3", "SNM_경강선_B3_PLATFORM_PANGYO", avoid_stairs_and_es=False)
    print_result("TEST 2-1. [성남역] 3번 출구 -> 판교방면 승강장 (일반인)", r2_gen)

    # 2-2. 1·4번 EV접근점 -> 판교방면 (휠체어)
    r2_wheelchair = dijkstra_find_path("SNM_1F_EV_ACCESS_1_4", "SNM_경강선_B3_PLATFORM_PANGYO", avoid_stairs_and_es=True)
    print_result("TEST 2-2. [성남역] 1·4번 선큰 지상 EV -> 판교방면 승강장 (휠체어)", r2_wheelchair)

if __name__ == "__main__":
    run_tests()