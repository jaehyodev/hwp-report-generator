#!/usr/bin/env python3
"""JSON 파싱 로깅 테스트 스크립트"""
import sys
import logging
import json
from pathlib import Path

# 경로 설정
sys.path.insert(0, str(Path(__file__).parent / "backend"))

# 로깅 설정 (DEBUG 레벨로)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from app.models.report_section import StructuredReportResponse, SectionMetadata, SectionType, SourceType
from app.utils.claude_client import ClaudeClient

# 테스트용 Claude JSON 응답 시뮬레이션
test_json_response = {
    "sections": [
        {
            "id": "TITLE",
            "type": "TITLE",
            "content": "2025년 AI 시장 분석 보고서",
            "order": 1,
            "source_type": "basic"
        },
        {
            "id": "BACKGROUND",
            "type": "SECTION",  # ← 주목: "SECTION"이라고 됨
            "content": "AI 시장이 급속도로 성장하고 있습니다. 2025년 글로벌 AI 시장은 300억 달러 규모로...",
            "order": 3,
            "source_type": "basic"
        },
        {
            "id": "MAIN_CONTENT",
            "type": "SECTION",
            "content": "주요 세그먼트별 분석: 1) 제너러티브 AI는 71억 달러에서... 2) 의료 산업이 39% CAGR...",
            "order": 4,
            "source_type": "basic"
        },
        {
            "id": "SUMMARY",
            "type": "SUMMARY",  # ← 주목: "SUMMARY" 타입
            "content": "전체 내용의 핵심 요약입니다.",
            "order": 5,
            "source_type": "basic"
        },
        {
            "id": "CONCLUSION",
            "type": "CONCLUSION",  # ← 주목: "CONCLUSION" 타입
            "content": "결론 및 제언 내용입니다.",
            "order": 6,
            "source_type": "basic"
        }
    ]
}

print("=" * 80)
print("테스트: Claude JSON 응답 파싱 (Enum 변환 로깅)")
print("=" * 80)
print()

# JSON 로깅
print("[INPUT] Claude JSON 응답:")
print(json.dumps(test_json_response, indent=2, ensure_ascii=False))
print()

# ClaudeClient 인스턴스 생성 및 _process_json_response 호출
try:
    print("[PROCESSING] _process_json_response() 호출 중...\n")
    claude = ClaudeClient()
    response = claude._process_json_response(test_json_response, topic="AI 시장 분석")

    print("\n" + "=" * 80)
    print("[OUTPUT] 파싱 결과")
    print("=" * 80)
    print(f"✅ 파싱 성공! 섹션 개수: {len(response.sections)}")
    print()

    for idx, section in enumerate(response.sections, 1):
        print(f"[섹션 {idx}]")
        print(f"  - ID: {section.id}")
        print(f"  - Type: {section.type} ({section.type.value if hasattr(section.type, 'value') else section.type})")
        print(f"  - SourceType: {section.source_type} ({section.source_type.value if hasattr(section.source_type, 'value') else section.source_type})")
        print(f"  - Order: {section.order}")
        print(f"  - Content: {section.content[:50]}..." if len(section.content) > 50 else f"  - Content: {section.content}")
        print()

except Exception as e:
    print(f"\n❌ 파싱 실패!")
    print(f"에러: {str(e)}")
    import traceback
    traceback.print_exc()

print("=" * 80)
