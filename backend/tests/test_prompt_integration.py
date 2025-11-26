"""
System Prompt 통합 기능 테스트

이 파일은 07.PromptIntegrate.md 계획에 따라 구현된 기능들을 테스트합니다.
"""
import pytest
from app.utils.prompts import get_default_report_prompt, create_topic_context_message
from app.utils.markdown_parser import (
    parse_markdown_to_content,
    extract_all_h2_sections,
    classify_section,
    extract_title_from_markdown
)


class TestPrompts:
    """System Prompt 관련 테스트"""

    def test_system_prompt_exists(self):
        """FINANCIAL_REPORT_SYSTEM_PROMPT가 정의되어 있는지 확인"""
        default_prompt = get_default_report_prompt()
        assert default_prompt is not None
        assert len(default_prompt) > 0
        assert "금융 기관" in default_prompt
        assert "Markdown" in default_prompt

    def test_system_prompt_structure(self):
        """System Prompt가 필요한 구조를 포함하는지 확인"""
        prompt = get_default_report_prompt()

        # 4개 섹션이 모두 언급되어야 함
        assert "요약" in prompt
        assert "배경" in prompt
        assert "주요" in prompt or "주요 내용" in prompt or "주요내용" in prompt
        assert "결론" in prompt

    def test_create_topic_context_message(self):
        """Topic Context Message 생성 테스트"""
        topic = "디지털뱅킹 트렌드"
        msg = create_topic_context_message(topic)

        # 기본 구조 확인
        assert msg["role"] == "user"
        assert "content" in msg
        assert isinstance(msg["content"], str)

        # 내용 확인
        assert topic in msg["content"]
        assert "대화 주제" in msg["content"]
        assert "이전 메시지" in msg["content"]

    def test_create_topic_context_message_with_special_chars(self):
        """특수 문자가 포함된 주제로 Context Message 생성"""
        topic = "2025년 디지털뱅킹 & AI 트렌드 분석 (상반기)"
        msg = create_topic_context_message(topic)

        assert msg["role"] == "user"
        assert topic in msg["content"]


class TestMarkdownParser:
    """Markdown 파싱 관련 테스트"""

    def test_parse_markdown_basic(self):
        """기본 Markdown 파싱 테스트"""
        md = """# 2025 디지털뱅킹 보고서

## 핵심 요약
디지털 전환이 가속화되고 있습니다.
모바일 뱅킹 사용자가 증가하고 있습니다.

## 추진 배경
금융권의 변화가 필요합니다.

## 주요 분석 결과
모바일 뱅킹이 성장하고 있습니다.

## 향후 계획
AI 도입을 추진합니다.
"""

        content = parse_markdown_to_content(md)

        # 제목
        assert content["title"] == "2025 디지털뱅킹 보고서"

        # 섹션 제목 (동적 추출)
        assert content["title_summary"] == "핵심 요약"
        assert content["title_background"] == "추진 배경"
        assert content["title_main_content"] == "주요 분석 결과"
        assert content["title_conclusion"] == "향후 계획"

        # 섹션 내용
        assert "디지털 전환" in content["summary"]
        assert "금융권의 변화" in content["background"]
        assert "모바일 뱅킹이 성장" in content["main_content"]
        assert "AI 도입" in content["conclusion"]

    def test_parse_markdown_english_sections(self):
        """영문 섹션 제목 파싱 테스트"""
        md = """# Digital Banking Report 2025

## Executive Summary
Digital transformation is accelerating.

## Background and Purpose
Financial sector needs innovation.

## Main Analysis
Mobile banking is growing.

## Recommendations
Implement AI solutions.
"""

        content = parse_markdown_to_content(md)

        assert content["title"] == "Digital Banking Report 2025"
        assert content["title_summary"] == "Executive Summary"
        assert content["title_background"] == "Background and Purpose"
        assert content["title_main_content"] == "Main Analysis"
        assert content["title_conclusion"] == "Recommendations"

    def test_extract_all_h2_sections(self):
        """H2 섹션 추출 테스트"""
        md = """# Title

## Section 1
Content 1

## Section 2
Content 2

## Section 3
Content 3
"""

        sections = extract_all_h2_sections(md)

        assert len(sections) == 3
        assert sections[0] == ("Section 1", "Content 1")
        assert sections[1] == ("Section 2", "Content 2")
        assert sections[2] == ("Section 3", "Content 3")

    def test_classify_section_summary(self):
        """요약 섹션 분류 테스트"""
        assert classify_section("요약") == "summary"
        assert classify_section("핵심 요약") == "summary"
        assert classify_section("Executive Summary") == "summary"
        assert classify_section("개요") == "summary"

    def test_classify_section_background(self):
        """배경 섹션 분류 테스트"""
        assert classify_section("배경 및 목적") == "background"
        assert classify_section("추진 배경") == "background"
        assert classify_section("사업 배경") == "background"
        assert classify_section("Background") == "background"

    def test_classify_section_main_content(self):
        """주요 내용 섹션 분류 테스트"""
        assert classify_section("주요 내용") == "main_content"
        assert classify_section("분석 결과") == "main_content"
        assert classify_section("세부 내역") == "main_content"
        assert classify_section("Main Analysis") == "main_content"

    def test_classify_section_conclusion(self):
        """결론 섹션 분류 테스트"""
        assert classify_section("결론 및 제언") == "conclusion"
        assert classify_section("향후 계획") == "conclusion"
        assert classify_section("시사점") == "conclusion"
        assert classify_section("Recommendations") == "conclusion"

    def test_classify_section_unknown(self):
        """알 수 없는 섹션 분류 테스트"""
        assert classify_section("참고 자료") == "unknown"
        assert classify_section("부록") == "unknown"

    def test_extract_title_from_markdown(self):
        """제목 추출 테스트"""
        md1 = "# 2025 디지털뱅킹 보고서\n\n내용..."
        assert extract_title_from_markdown(md1) == "2025 디지털뱅킹 보고서"

        md2 = "내용만 있고 제목이 없음"
        assert extract_title_from_markdown(md2) == "보고서"

    def test_parse_markdown_no_sections(self):
        """섹션이 없는 경우 main_content로 fallback"""
        md = """# 단순 보고서

이것은 섹션 구분 없이 작성된 보고서입니다.
모든 내용이 하나로 이어져 있습니다.
"""

        content = parse_markdown_to_content(md)

        assert content["title"] == "단순 보고서"
        assert len(content["main_content"]) > 0
        assert "섹션 구분 없이" in content["main_content"]

    def test_parse_markdown_multiline_content(self):
        """여러 줄의 내용이 있는 섹션 파싱"""
        md = """# 보고서

## 요약

첫 번째 단락입니다.

두 번째 단락입니다.

세 번째 단락입니다.

## 배경

배경 내용입니다.
"""

        content = parse_markdown_to_content(md)

        assert "첫 번째" in content["summary"]
        assert "두 번째" in content["summary"]
        assert "세 번째" in content["summary"]


class TestMessageConstruction:
    """Message 배열 구성 테스트"""

    def test_topic_context_message_structure(self):
        """Topic Context Message가 올바른 구조를 갖는지 확인"""
        topic = "디지털뱅킹 트렌드"
        msg = create_topic_context_message(topic)

        # Claude API 메시지 형식 준수
        assert "role" in msg
        assert "content" in msg
        assert msg["role"] in ["user", "assistant", "system"]
        assert isinstance(msg["content"], str)

    def test_messages_array_with_topic_context(self):
        """Topic Context가 첫 번째 메시지로 올바르게 추가되는지 확인"""
        topic = "디지털뱅킹 트렌드"
        topic_msg = create_topic_context_message(topic)

        user_messages = [
            {"role": "user", "content": "보고서를 작성해주세요."},
            {"role": "assistant", "content": "네, 작성하겠습니다."},
            {"role": "user", "content": "주요 내용을 더 상세히 써주세요."}
        ]

        claude_messages = [topic_msg] + user_messages

        # 구조 검증
        assert len(claude_messages) == 4
        assert claude_messages[0] == topic_msg
        assert claude_messages[0]["role"] == "user"
        assert topic in claude_messages[0]["content"]


class TestIntegration:
    """통합 테스트"""

    def test_end_to_end_markdown_flow(self):
        """Markdown 생성 → 파싱 → HWP 템플릿 치환 흐름 테스트"""
        # 1. Claude가 생성했다고 가정하는 Markdown
        md_output = """# 2025 디지털뱅킹 트렌드 보고서

## 핵심 요약

2025년 디지털뱅킹 산업은 AI와 빅데이터를 중심으로 혁신을 가속화하고 있습니다.
모바일 뱅킹 사용자가 전년 대비 30% 증가하며 시장을 주도하고 있습니다.

## 추진 배경 및 필요성

금융권의 디지털 전환이 필수적인 상황입니다.
고객 경험 개선과 운영 효율성 향상을 위해 디지털 기술 도입이 시급합니다.

## 주요 분석 결과

### 1. 모바일 뱅킹 성장
모바일 뱅킹 거래액이 전년 대비 40% 증가했습니다.

### 2. AI 챗봇 도입
대형 은행들이 AI 챗봇을 도입하여 고객 상담 시간을 50% 단축했습니다.

### 3. 오픈뱅킹 확산
오픈뱅킹 API 연동 서비스가 200여 개로 증가했습니다.

## 향후 추진 계획

AI 기반 개인화 서비스를 확대하고, 블록체인 기술을 활용한 보안 강화를 추진할 예정입니다.
디지털 금융 리터러시 교육도 함께 진행하겠습니다.
"""

        # 2. Markdown 파싱
        content = parse_markdown_to_content(md_output)

        # 3. HWP 템플릿에 필요한 모든 필드 확인
        required_fields = [
            "title", "summary", "background", "main_content", "conclusion",
            "title_summary", "title_background", "title_main_content", "title_conclusion"
        ]

        for field in required_fields:
            assert field in content
            assert len(content[field]) > 0, f"{field} is empty"

        # 4. 실제 값 검증
        assert content["title"] == "2025 디지털뱅킹 트렌드 보고서"
        assert content["title_summary"] == "핵심 요약"
        assert content["title_background"] == "추진 배경 및 필요성"
        assert content["title_main_content"] == "주요 분석 결과"
        assert content["title_conclusion"] == "향후 추진 계획"

        assert "AI와 빅데이터" in content["summary"]
        assert "디지털 전환" in content["background"]
        assert "모바일 뱅킹 거래액" in content["main_content"]
        assert "블록체인 기술" in content["conclusion"]

    def test_system_prompt_purity(self):
        """System Prompt가 순수하게 지침만 포함하는지 확인"""
        prompt = get_default_report_prompt()

        # Topic이나 구체적인 데이터가 포함되어서는 안 됨
        assert "디지털뱅킹" not in prompt
        assert "2025" not in prompt
        assert "트렌드" not in prompt

        # 지침만 포함
        assert "당신은" in prompt
        assert "작성" in prompt
        assert "형식" in prompt or "Markdown" in prompt
