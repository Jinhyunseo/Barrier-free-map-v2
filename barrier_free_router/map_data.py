# map_data.py

sample_map = {
    'A_출발지': [
        {
            'to': 'B_일반버스정류장',
            'type': 'walk',
            'travel_time_min': 5,
            'walk_distance_m': 300,
            'has_stairs': False,
            'has_escalator': False,
            'incline': 2.0,
            'is_transfer': False,
            'has_elevator': False
        },
        {
            'to': 'C_지하철역_입구',
            'type': 'walk',
            'travel_time_min': 8,
            'walk_distance_m': 450,
            'has_stairs': True,
            'has_escalator': False,
            'incline': 1.0,
            'is_transfer': False,
            'has_elevator': False
        },
        {
            'to': 'D_완만보행로',
            'type': 'walk',
            'travel_time_min': 10,
            'walk_distance_m': 500,
            'has_stairs': False,
            'has_escalator': False,
            'incline': 1.5,
            'is_transfer': False,
            'has_elevator': False
        }
    ],
    # map_data.py 예시
    'B_일반버스정류장': [
    {
        'to': 'E_환승센터',
        'type': 'bus',
        'travel_time_min': 15,
        'walk_distance_m': 0,
        'has_stairs': False,
        'has_escalator': False,
        'incline': 0.0,
        'is_transfer': False,
        'has_elevator': False,
        'is_low_floor_bus': True   # ⭕ 저상버스 여부 (True / False)
    }
],
    'C_지하철역_입구': [
        {
            'to': 'E_환승센터',
            'type': 'subway',
            'travel_time_min': 10,
            'walk_distance_m': 50,
            'has_stairs': False,
            'has_escalator': True,
            'incline': 0.0,
            'is_transfer': False,
            'has_elevator': True
        }
    ],
    'D_완만보행로': [
        {
            'to': 'E_환승센터',
            'type': 'subway',
            'travel_time_min': 12,
            'walk_distance_m': 100,
            'has_stairs': False,
            'has_escalator': False,
            'incline': 0.0,
            'is_transfer': False,
            'has_elevator': True
        }
    ],
    'E_환승센터': [
        {
            'to': 'F_도착지',
            'type': 'walk',
            'travel_time_min': 5,
            'walk_distance_m': 200,
            'has_stairs': False,
            'has_escalator': False,
            'incline': 2.0,
            'is_transfer': True,
            'has_elevator': True
        }
    ],
    'F_도착지': []
}