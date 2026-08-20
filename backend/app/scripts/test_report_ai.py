from __future__ import annotations

import argparse
import asyncio
import mimetypes
from pathlib import Path

from app.core.config import settings
from app.services.report_ai_service import verify_report_image


async def main() -> None:
    parser = argparse.ArgumentParser(description="실제 Gemini 사진 제보 검수 단독 테스트")
    parser.add_argument("image", type=Path, help="테스트할 이미지 파일 경로")
    parser.add_argument("--report-type", default="ELEVATOR_OUT")
    parser.add_argument("--title", default="엘리베이터 고장 테스트")
    parser.add_argument("--description", default="배포 전 AI 검수 테스트")
    parser.add_argument("--location", default="테스트 위치")
    args = parser.parse_args()

    if not settings.GEMINI_API_KEY:
        raise SystemExit("GEMINI_API_KEY가 .env에 설정되어 있지 않습니다.")
    if not args.image.is_file():
        raise SystemExit(f"이미지 파일을 찾을 수 없습니다: {args.image}")

    mime_type = mimetypes.guess_type(args.image.name)[0] or "image/jpeg"
    result = await verify_report_image(
        image_bytes=args.image.read_bytes(),
        mime_type=mime_type,
        report_type=args.report_type,
        title=args.title,
        description=args.description,
        location_text=args.location,
    )

    if result is None:
        raise SystemExit("Gemini 호출/응답 검증 실패: 서버 로그를 확인하세요.")

    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
