# 프로젝트 데이터 디렉터리

이 폴더는 FastAPI 백엔드가 사용하는 **정적 데이터와 역사 상태 스냅샷의 단일 저장 위치**입니다.
JSON/GeoJSON 데이터는 다른 프로젝트 루트나 `backend/data`에 복사하지 않고 이 폴더 아래에만 둡니다.

## 구조

```text
app/data/
├─ bus/
│  ├─ bus_stops.json                 # 성남시 버스 정류장 정보
│  └─ bus_routes.json                # 성남시/경기도 버스 노선 정보
├─ walking/
│  └─ seongnam_walking_network.geojson # 성남시 보행망
└─ stations/
   ├─ facilities/
   │  ├─ station_facilities.json     # 전체 역사 EV/ES 통합 시설 정보 (DB seed 기준)
   │  ├─ by_line/                    # 일부 역/노선별 원본 또는 비교 데이터
   │  └─ legacy/                     # 과거 형식 데이터(참고용)
   ├─ realtime/
   │  ├─ current/                    # 서비스가 우선 사용하는 최신 장비 상태 스냅샷
   │  └─ archive/                    # 과거/매칭 전 스냅샷
   └─ graphs/
      ├─ v1/
      │  ├─ all_stations_graph.json  # 기존 통합 역사 내부 그래프
      │  └─ individual/              # 기존 역별 그래프
      ├─ v2/                         # 신형 역사 내부 그래프
      └─ debug/                      # 디버깅 산출물
```

## 코드에서 경로를 사용할 때

경로를 직접 문자열로 만들지 말고 `app/core/data_paths.py`의 상수를 사용합니다.

예:

```python
from app.core.data_paths import BUS_STOPS_FILE, STATION_FACILITIES_FILE
```

## DB 초기 데이터

`python -m app.scripts.seed_data`는 아래 표준 데이터만 읽습니다.

- `bus/bus_routes.json`
- `bus/bus_stops.json`
- `stations/facilities/station_facilities.json`
- `stations/realtime/current/*.json`

`legacy`, `archive`, 역사 그래프 JSON은 DB seed 대상으로 사용하지 않습니다.
