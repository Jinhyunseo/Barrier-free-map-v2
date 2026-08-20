from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")


class Settings:
    PROJECT_NAME = os.getenv("PROJECT_NAME", "Barrier-Free Navigation API")
    VERSION = os.getenv("VERSION", "0.2.0")

    # Local 개발에서는 SQLite를 사용할 수 있고, Cloud SQL에서는 mysql+asyncmy URL을 넣습니다.
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        f"sqlite+aiosqlite:///{(BACKEND_DIR / 'barrier_free.db').as_posix()}",
    )
    SQL_ECHO = os.getenv("SQL_ECHO", "false").lower() == "true"
    AUTO_CREATE_TABLES = os.getenv("AUTO_CREATE_TABLES", "false").lower() == "true"

    DEFAULT_REPORT_USER_ID = int(os.getenv("DEFAULT_REPORT_USER_ID", "1"))
    MAX_REPORT_IMAGE_MB = int(os.getenv("MAX_REPORT_IMAGE_MB", "10"))

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    REPORT_GEMINI_MODEL = os.getenv("REPORT_GEMINI_MODEL", "gemini-3.5-flash")
    REPORT_AI_ACCEPT_THRESHOLD = float(os.getenv("REPORT_AI_ACCEPT_THRESHOLD", "0.65"))


settings = Settings()
