from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.api.reports import _decide_report_status
from app.services import report_ai_service as svc
from app.services.report_ai_service import ReportAiResult


class FakePart:
    @staticmethod
    def from_text(*, text):
        return ("text", text)

    @staticmethod
    def from_bytes(*, data, mime_type):
        return ("bytes", len(data), mime_type)


class FakeTypes:
    Part = FakePart

    class GenerateContentConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs


class FakeModels:
    def __init__(self, sequence):
        self.sequence = list(sequence)
        self.calls = 0

    async def generate_content(self, **kwargs):
        self.calls += 1
        value = self.sequence.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


class FakeClient:
    def __init__(self, sequence):
        self.models = FakeModels(sequence)
        self.aio = SimpleNamespace(models=self.models)


def response(text: str):
    return SimpleNamespace(text=text, parsed=None, candidates=[])


def valid_json(status="BROKEN", equipment="ELEVATOR", verification="ACCEPTED", confidence=0.91):
    return (
        '{"verification":"%s","confidence_score":%s,'
        '"detected_status":"%s","detected_equipment_type":"%s",'
        '"reason":"사진에서 관련 시설의 장애 정황이 확인됩니다."}'
        % (verification, confidence, status, equipment)
    )


def run_verify(sequence):
    fake_client = FakeClient(sequence)
    old_client = svc._client
    old_types = svc.genai_types
    try:
        svc._client = fake_client
        svc.genai_types = FakeTypes
        result = asyncio.run(
            svc.verify_report_image(
                image_bytes=b"fake-image",
                mime_type="image/jpeg",
                report_type="ELEVATOR_OUT",
                title="야탑역 엘리베이터 고장",
                description="테스트",
                location_text="야탑역 2번 출구",
            )
        )
        return result, fake_client.models.calls
    finally:
        svc._client = old_client
        svc.genai_types = old_types


def test_valid_response_returns_on_first_call():
    result, calls = run_verify([response(valid_json())])
    assert result is not None
    assert result.verification == "ACCEPTED"
    assert result.detected_status == "BROKEN"
    assert calls == 1


def test_truncated_json_retries_once_then_succeeds():
    result, calls = run_verify([
        response('{"verification":"ACCEPTED","confidence_score":0.9'),
        response(valid_json()),
    ])
    assert result is not None
    assert result.detected_status == "BROKEN"
    assert calls == 2


def test_two_api_failures_return_none():
    result, calls = run_verify([RuntimeError("temporary"), RuntimeError("temporary")])
    assert result is None
    assert calls == 2


def test_schema_rejects_invalid_values():
    assert svc._parse_response(response(valid_json(confidence=1.5))) is None
    assert svc._parse_response(response(valid_json(verification="YES"))) is None


def test_report_status_requires_actual_issue_state():
    broken = ReportAiResult(
        verification="ACCEPTED",
        confidence_score=0.91,
        detected_status="BROKEN",
        detected_equipment_type="ELEVATOR",
        reason="고장 정황 확인",
    )
    normal = ReportAiResult(
        verification="ACCEPTED",
        confidence_score=0.91,
        detected_status="NORMAL",
        detected_equipment_type="ELEVATOR",
        reason="정상 운행으로 보임",
    )
    wrong_equipment = ReportAiResult(
        verification="ACCEPTED",
        confidence_score=0.91,
        detected_status="BROKEN",
        detected_equipment_type="ESCALATOR",
        reason="에스컬레이터 장애",
    )
    assert _decide_report_status("ELEVATOR_OUT", broken) == "ACCEPTED"
    assert _decide_report_status("ELEVATOR_OUT", normal) == "PENDING_REVIEW"
    assert _decide_report_status("ELEVATOR_OUT", wrong_equipment) == "PENDING_REVIEW"
