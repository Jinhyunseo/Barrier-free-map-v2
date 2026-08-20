# gemini_explain.py
import json
import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client()

def generate_route_reason(selected_conditions, preference, route_result):
    system_instruction = """
    너는 교통약자 및 이동약자를 위한 배리어 프리 길안내 앱의 AI 도우미야.
    사용자가 선택한 '이동 조건'과 '경로 선호도', 그리고 탐색된 경로 결과를 바탕으로
    왜 이 경로가 추천되었는지 자연스럽고 친절하게 설명해야 해.

    [가이드라인]
    1. 정중하고 친절한 존댓말(~해요, ~합니다)을 사용한다.
    2. 사용자가 선택한 이동 조건(예: 계단 회피, 엘리베이터 필수 등)이 잘 반영되었음을 강조한다.
    3. 글자 수는 100자 내외(2~3문장)로 간결하게 작성한다.
    4. 부연 설명 없이 '추천 이유 문장'만 출력한다.
    """

    prompt_data = {
        "user_selected_conditions": selected_conditions,
        "user_preference": preference,
        "route_summary": {
            "total_time_min": route_result['total_time_min'],
            "total_walk_m": route_result['total_walk_m'],
            "transfers": route_result['transfers'],
            "path_nodes": route_result['path']
        }
    }

    response = client.models.generate_content(
        model='gemini-3.5-flash',
        contents=f"다음 결과를 바탕으로 추천 이유를 만들어주세요:\n{json.dumps(prompt_data, ensure_ascii=False)}",
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.3,
        )
    )

    return response.text.strip()