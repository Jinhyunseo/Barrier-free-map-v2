# 배포 직전 빠른 실행 순서

## 1. Cloud SQL에 DB 생성

```sql
CREATE DATABASE barrier_free
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
```

## 2. backend/.env 설정

`.env.example`을 `.env`로 복사한 뒤 최소한 아래 값을 설정합니다.

```env
DATABASE_URL=mysql+asyncmy://DB_USER:URL_ENCODED_PASSWORD@CLOUD_SQL_PUBLIC_IP:3306/barrier_free?charset=utf8mb4
SQL_ECHO=false
AUTO_CREATE_TABLES=false
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
REPORT_GEMINI_MODEL=gemini-3.5-flash
REPORT_AI_ACCEPT_THRESHOLD=0.65
```

`.env`는 Git에 올리지 않습니다. 프로젝트 `.gitignore`에 이미 제외되어 있습니다.

## 3. 패키지 설치

```bash
cd backend
python -m pip install -r requirements.txt
```

## 4. 테이블 생성 및 데이터 시드

```bash
python -m app.scripts.init_db
python -m app.scripts.seed_data
```

## 5. DB 배포 전 점검

```bash
python -m app.scripts.deployment_preflight
```

DB 연결 성공 여부와 사용자/교통수단/시설/장비/상태/제보 건수를 출력합니다.

## 6. Gemini 사진 검수 단독 실서버 테스트

실제 고장/점검 사진 한 장을 준비한 뒤:

```bash
python -m app.scripts.test_report_ai "C:/path/to/photo.jpg" --report-type ELEVATOR_OUT --title "야탑역 엘리베이터 고장" --location "야탑역 2번 출구"
```

JSON 결과가 출력되면 Gemini API 연결 + 이미지 입력 + 구조화 응답 검증이 모두 정상입니다.

## 7. FastAPI 실행

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

확인:
- `/health`
- `/docs`
- `POST /users/register`
- `GET /facilities/search`
- `GET /facilities/{facility_id}/equipment`
- `POST /reports`

## 사진 제보 상태 반영 규칙

- Gemini 호출 실패/응답 오류 -> `PENDING_REVIEW`, 기존 시설 상태 변경 안 함
- 관련 사진이지만 상태 불명확 -> `PENDING_REVIEW`
- 명확한 무관 사진 -> `REJECTED`
- 충분한 신뢰도로 `BROKEN`/`MAINTENANCE`/`BLOCKED` 확인 -> `ACCEPTED`
- `ACCEPTED` + 장비 특정 성공 -> `equipment_status`에 `USER_REPORT_AI` 이력 추가
- 엘리베이터/에스컬레이터 제보인데 장비 특정 실패 -> 역 전체를 고장으로 표시하지 않음
