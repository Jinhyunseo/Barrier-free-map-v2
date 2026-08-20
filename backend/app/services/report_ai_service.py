from __future__ import annotations

import json
import logging
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:  # pragma: no cover
    genai = None
    genai_types = None

logger = logging.getLogger(__name__)


class ReportAiResult(BaseModel):
    verification: Literal["ACCEPTED", "REVIEW_REQUIRED", "REJECTED"] = Field(
        description="사진이 제보 내용과 관련 있고 판별 가능한지에 대한 검수 결과"
    )
    confidence_score: float = Field(ge=0.0, le=1.0, description="판정 신뢰도 0~1")
    detected_status: Literal["NORMAL", "BROKEN", "MAINTENANCE", "BLOCKED", "UNKNOWN"] = Field(
        description="사진에서 추정한 시설/장비 상태"
    )
    detected_equipment_type: Literal[
        "ELEVATOR", "ESCALATOR", "STAIRS", "ROAD", "OTHER", "UNKNOWN"
    ] = Field(description="사진에서 확인된 대상 종류")
    reason: str = Field(min_length=1, max_length=300, description="한국어 한 문장의 간단한 판정 이유")


_client: Any = None


SYSTEM_INSTRUCTION = """\
당신은 교통약자 길안내 서비스의 현장 제보 사진을 보조 검수합니다.
엄격한 신원/장소 증명보다 사진이 제보 내용과 관련 있는지, 그리고 장애 상태를 합리적으로 확인할 수 있는지 판단하세요.

판정 원칙:
- 역명판이나 정확한 시설 번호가 사진에 없다는 이유만으로 거절하지 마세요.
- 관련 시설이 보이지만 고장/통제 여부가 불확실하면 수동 검수가 필요하다고 판단하세요.
- 물리적 차단, 공사 흔적, 운행 중지 안내, 명확한 고장 정황이 보이면 문제 상태로 판단할 수 있습니다.
- 전혀 무관한 사진, 심하게 깨진 이미지, 대상 자체를 확인하기 어려운 경우에만 거절하세요.
- location_text는 참고 정보이며 사진 안에서 장소명을 반드시 확인할 필요는 없습니다.
- 판정 이유는 한국어 한 문장으로 짧게 작성하세요.
- 제공된 구조화 출력 스키마를 정확히 따르세요.
"""


def _get_client():
    global _client
    if _client is not None:
        return _client
    if genai is None or not settings.GEMINI_API_KEY:
        return None
    try:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    except Exception:
        logger.exception("Gemini report client initialization failed")
        return None
    return _client


def _response_finish_reason(response: Any) -> str | None:
    try:
        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            return None
        value = getattr(candidates[0], "finish_reason", None)
        return str(value) if value is not None else None
    except Exception:
        return None


def _parse_response(response: Any) -> ReportAiResult | None:
    parsed = getattr(response, "parsed", None)
    if parsed is not None:
        try:
            return ReportAiResult.model_validate(parsed)
        except ValidationError:
            logger.warning("Gemini parsed response did not match ReportAiResult schema")

    raw = (getattr(response, "text", "") or "").strip()
    if not raw:
        return None

    cleaned = raw.replace("```json", "").replace("```", "").strip()
    try:
        return ReportAiResult.model_validate_json(cleaned)
    except ValidationError as exc:
        logger.warning(
            "Gemini returned invalid/truncated JSON; finish_reason=%s; raw=%r; error=%s",
            _response_finish_reason(response),
            cleaned[:500],
            exc,
        )
        return None


def _make_config(*, temperature: float):
    return genai_types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=ReportAiResult,
        temperature=temperature,
        max_output_tokens=2048,
    )


async def verify_report_image(
    *,
    image_bytes: bytes,
    mime_type: str,
    report_type: str,
    title: str,
    description: str | None,
    location_text: str | None,
) -> ReportAiResult | None:
    client = _get_client()
    if client is None or genai_types is None:
        return None

    payload = {
        "report_type": report_type,
        "title": title,
        "description": description,
        "location_text": location_text,
    }

    contents = [
        genai_types.Part.from_text(text=json.dumps(payload, ensure_ascii=False)),
        genai_types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
    ]

    # 정상 응답은 1회 호출로 끝내고, 잘린 JSON/스키마 불일치/일시적 API 오류일 때만 한 번 재시도합니다.
    for attempt, temperature in enumerate((0.2, 0.0), start=1):
        try:
            response = await client.aio.models.generate_content(
                model=settings.REPORT_GEMINI_MODEL,
                contents=contents,
                config=_make_config(temperature=temperature),
            )
            result = _parse_response(response)
            if result is not None:
                return result
        except Exception:
            logger.exception("Gemini report image verification attempt %s failed", attempt)

        if attempt == 1:
            logger.warning("Retrying Gemini report image verification once")

    return None
