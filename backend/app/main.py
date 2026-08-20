from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.facilities import router as facilities_router
from app.api.geocode import router as geocode_router
from app.api.reports import router as reports_router
from app.api.route import router as route_router
from app.api.users import router as users_router
from app.core.config import BACKEND_DIR, settings
from app.core.database import create_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.AUTO_CREATE_TABLES:
        await create_tables()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="교통약자 맞춤형 경로 추천 + 사진 제보 서비스 백엔드",
    version=settings.VERSION,
    lifespan=lifespan,
)


# Flutter/Web 프론트엔드가 FastAPI에 요청할 수 있도록 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 개발 단계. 운영에서는 실제 프론트 도메인으로 제한 권장
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 제보 이미지 정적 제공
STATIC_DIR = Path(BACKEND_DIR) / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# API 라우터 연결
app.include_router(route_router)
app.include_router(geocode_router)
app.include_router(facilities_router)
app.include_router(users_router)
app.include_router(reports_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Barrier-Free Navigation API is running!"}


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
