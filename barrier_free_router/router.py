# router.py
import heapq
from constraints import check_hard_barrier

# 선호도별 가중치 테이블 (Soft Constraints)
PREFERENCE_WEIGHTS = {
    '추천':      {'time': 1.0, 'walk': 0.05, 'transfer': 15.0},
    '최단 시간':  {'time': 2.0, 'walk': 0.01, 'transfer': 5.0},
    '최소 도보':  {'time': 0.5, 'walk': 0.15, 'transfer': 10.0},
    '최소 환승':  {'time': 1.0, 'walk': 0.03, 'transfer': 30.0}
}

def find_optimal_route(graph, start, end, constraints, preference):
    weights = PREFERENCE_WEIGHTS[preference]
    pq = [(0.0, start, [start], 0, 0, 0)]  # (점수, 현재노드, 경로, 누적시간, 누적도보, 누적환승)
    
    best_scores = {node: float('inf') for node in graph}
    best_scores[start] = 0.0

    while pq:
        score, current, path, time, walk, transfers = heapq.heappop(pq)

        if score > best_scores[current]:
            continue

        if current == end:
            return {
                'score': round(score, 2),
                'path': path,
                'total_time_min': time,
                'total_walk_m': walk,
                'transfers': transfers
            }

        for edge in graph[current]:
            # 1. Hard Constraint 검사 (constraints.py)
            if check_hard_barrier(edge, constraints):
                continue

            # 2. Preference 가중치 반영 (Soft Constraint 점수 계산)
            edge_transfers = 1 if edge['is_transfer'] else 0
            edge_score = (
                edge['travel_time_min'] * weights['time'] +
                edge['walk_distance_m'] * weights['walk'] +
                edge_transfers * weights['transfer']
            )
            
            new_score = score + edge_score
            next_node = edge['to']

            if new_score < best_scores[next_node]:
                best_scores[next_node] = new_score
                heapq.heappush(pq, (
                    new_score, 
                    next_node, 
                    path + [next_node], 
                    time + edge['travel_time_min'], 
                    walk + edge['walk_distance_m'],
                    transfers + edge_transfers
                ))

    return None