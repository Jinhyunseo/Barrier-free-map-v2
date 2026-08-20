# Barrier-free-map

성남시 교통약자를 위한 배리어프리 길안내 프로젝트입니다.

## 백엔드 데이터 위치

버스/정류장, 보행망, 지하철 역사 시설, 엘리베이터·에스컬레이터 상태, 역사 내부 그래프 JSON/GeoJSON은 모두 아래 한 곳에 정리되어 있습니다.

```text
backend/app/data/
```

세부 구조와 각 파일의 역할은 `backend/app/data/README.md`를 참고하세요.

백엔드 코드에서는 데이터 파일 경로를 직접 문자열로 만들지 않고 `backend/app/core/data_paths.py`의 상수를 사용합니다.

## 로컬 DB 초기화

`backend/.env`에 MySQL `DATABASE_URL`을 설정한 뒤 `backend` 폴더에서 실행합니다.

```bash
python -m app.scripts.init_db
python -m app.scripts.seed_data
python -m uvicorn app.main:app --reload
```

Swagger UI는 기본적으로 `http://127.0.0.1:8000/docs`에서 확인할 수 있습니다.
