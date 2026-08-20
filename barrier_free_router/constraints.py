# constraints.py

def check_hard_barrier(edge, constraints):
    """
    사용자가 선택한 이동 조건(Hard Constraint)을 위반하는지 검사하는 문지기 함수
    위반 시: 탈락 이유(문자열) 반환
    안전 시: None 반환
    """
    
def check_hard_barrier(edge, constraints):
    # 1. 계단 이용 어려움
    if constraints.get('no_stairs') and edge.get('has_stairs'):
        return "계단 구간"
    
    # 2. 에스컬레이터 이용 어려움
    if constraints.get('no_escalator') and edge.get('has_escalator'):
        return "에스컬레이터 구간"
    
    # 3. 급경사 피하기 (경사도 5% 이상)
    if constraints.get('avoid_slope') and edge.get('incline', 0) >= 5.0:
        return "급경사 구간"
    
    # 4. 엘리베이터 필수
    if constraints.get('need_elevator') and edge.get('type') in ['subway', 'walk_vertical'] and not edge.get('has_elevator'):
        return "엘리베이터 없음"
    
    # 5. [신규 추가] 저상 버스 필요
    # 버스(bus) 수단인데 저상버스가 아니라면(is_low_floor_bus == False) 통과 불가
    if constraints.get('require_low_floor_bus') and edge.get('type') == 'bus' and not edge.get('is_low_floor_bus', False):
        return "일반 버스 (저상버스 아님)"
    
    return None