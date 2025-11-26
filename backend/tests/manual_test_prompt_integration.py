"""
Prompt 통합 기능 수동 테스트 스크립트

이 스크립트는 개발자가 직접 실행하여 prompt 통합이 올바르게 동작하는지 확인할 수 있습니다.
각 테스트는 독립적으로 실행되며, 결과를 콘솔에 출력합니다.

실행 방법:
    cd backend
    uv run python tests/manual_test_prompt_integration.py
"""
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.utils.prompts import get_default_report_prompt, create_topic_context_message
from app.utils.markdown_parser import parse_markdown_to_content


def print_section(title):
    """섹션 제목 출력"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def test_1_topic_context_message():
    """테스트 1: Topic Context Message 생성"""
    print_section("TEST 1: Topic Context Message 생성")

    topic = "디지털뱅킹 트렌드"
    msg = create_topic_context_message(topic)

    print(f"\n[입력] Topic: {topic}")
    print(f"\n[출력] Message:")
    print(f"  Role: {msg['role']}")
    print(f"  Content:\n{msg['content']}")

    # 검증
    assert msg['role'] == 'user', "❌ Role이 'user'가 아닙니다."
    assert topic in msg['content'], "❌ Topic이 content에 포함되지 않았습니다."

    print("\n✅ 테스트 통과: Topic Context Message가 올바르게 생성되었습니다.")


def test_2_messages_construction():
    """테스트 2: Messages 배열 구성"""
    print_section("TEST 2: Messages 배열 구성")

    topic_msg = create_topic_context_message("디지털뱅킹 트렌드")
    user_messages = [
        {"role": "user", "content": "보고서를 작성해주세요."},
        {"role": "assistant", "content": "네, 작성하겠습니다."},
        {"role": "user", "content": "주요 내용을 더 상세히 써주세요."}
    ]

    claude_messages = [topic_msg] + user_messages

    print(f"\n[결과] 총 메시지 수: {len(claude_messages)}")
    print(f"\n첫 번째 메시지 (Topic Context):")
    print(f"  Role: {claude_messages[0]['role']}")
    print(f"  Content (앞 50자): {claude_messages[0]['content'][:50]}...")

    print(f"\n두 번째 메시지 (User):")
    print(f"  Role: {claude_messages[1]['role']}")
    print(f"  Content: {claude_messages[1]['content']}")

    default_prompt = get_default_report_prompt()
    print(f"\nSystem Prompt (앞 100자):")
    print(f"  {default_prompt[:100]}...")

    # 검증
    assert len(claude_messages) == 4, "❌ 메시지 수가 4개가 아닙니다."
    assert claude_messages[0]['role'] == 'user', "❌ 첫 번째 메시지 role이 'user'가 아닙니다."

    print("\n✅ 테스트 통과: Messages 배열이 올바르게 구성되었습니다.")


def test_3_markdown_parsing():
    """테스트 3: Markdown 파싱"""
    print_section("TEST 3: Markdown 파싱 (동적 섹션 제목 추출)")

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

    print(f"\n[파싱 결과]")
    print(f"\n제목: {content['title']}")
    print(f"\n섹션 제목들:")
    print(f"  요약: {content['title_summary']}")
    print(f"  배경: {content['title_background']}")
    print(f"  주요내용: {content['title_main_content']}")
    print(f"  결론: {content['title_conclusion']}")

    print(f"\n섹션 내용 (앞 30자):")
    print(f"  요약: {content['summary'][:30]}...")
    print(f"  배경: {content['background'][:30]}...")
    print(f"  주요내용: {content['main_content'][:30]}...")
    print(f"  결론: {content['conclusion'][:30]}...")

    # 검증
    assert content['title'] == "2025 디지털뱅킹 보고서", "❌ 제목이 올바르지 않습니다."
    assert content['title_summary'] == "핵심 요약", "❌ 요약 섹션 제목이 올바르지 않습니다."
    assert content['title_background'] == "추진 배경", "❌ 배경 섹션 제목이 올바르지 않습니다."
    assert content['title_main_content'] == "주요 분석 결과", "❌ 주요내용 섹션 제목이 올바르지 않습니다."
    assert content['title_conclusion'] == "향후 계획", "❌ 결론 섹션 제목이 올바르지 않습니다."

    print("\n✅ 테스트 통과: Markdown이 올바르게 파싱되었습니다.")


def test_4_english_sections():
    """테스트 4: 영문 섹션 제목 파싱"""
    print_section("TEST 4: 영문 섹션 제목 파싱")

    md = """# Digital Banking Report 2025

## Executive Summary
Digital transformation is accelerating.

## Background and Purpose
Financial sector needs innovation.

## Main Analysis
Mobile banking is growing rapidly.

## Recommendations
Implement AI solutions immediately.
"""

    content = parse_markdown_to_content(md)

    print(f"\n[파싱 결과]")
    print(f"\n제목: {content['title']}")
    print(f"\n섹션 제목들 (영문):")
    print(f"  Summary: {content['title_summary']}")
    print(f"  Background: {content['title_background']}")
    print(f"  Main Content: {content['title_main_content']}")
    print(f"  Conclusion: {content['title_conclusion']}")

    # 검증
    assert content['title'] == "Digital Banking Report 2025", "❌ 제목이 올바르지 않습니다."
    assert content['title_summary'] == "Executive Summary", "❌ Summary 제목이 올바르지 않습니다."
    assert "Background" in content['title_background'], "❌ Background 제목이 올바르지 않습니다."

    print("\n✅ 테스트 통과: 영문 섹션도 올바르게 파싱됩니다.")


def test_5_system_prompt_purity():
    """테스트 5: System Prompt 순수성 검증"""
    print_section("TEST 5: System Prompt 순수성 검증")

    prompt = get_default_report_prompt()

    print(f"\nSystem Prompt 길이: {len(prompt)} 문자")
    print(f"\nSystem Prompt 내용 (앞 200자):")
    print(prompt[:200] + "...")

    print(f"\n\n[검증 항목]")

    # Topic이 포함되지 않아야 함
    topic_keywords = ["디지털뱅킹", "트렌드", "2025년", "AI", "빅데이터"]
    has_topic = any(keyword in prompt for keyword in topic_keywords)
    print(f"  ✓ Topic 키워드 미포함: {'✅ 통과' if not has_topic else '❌ 실패'}")

    # 역할 정의가 있어야 함
    has_role = "당신은" in prompt or "you are" in prompt.lower()
    print(f"  ✓ 역할 정의 포함: {'✅ 통과' if has_role else '❌ 실패'}")

    # 형식 지침이 있어야 함
    has_format = "Markdown" in prompt or "형식" in prompt
    print(f"  ✓ 형식 지침 포함: {'✅ 통과' if has_format else '❌ 실패'}")

    # 섹션 구조가 명시되어야 함
    has_sections = "요약" in prompt and "배경" in prompt and "결론" in prompt
    print(f"  ✓ 섹션 구조 명시: {'✅ 통과' if has_sections else '❌ 실패'}")

    # 검증
    assert not has_topic, "❌ System Prompt에 Topic 키워드가 포함되어 있습니다."
    assert has_role, "❌ System Prompt에 역할 정의가 없습니다."
    assert has_format, "❌ System Prompt에 형식 지침이 없습니다."
    assert has_sections, "❌ System Prompt에 섹션 구조가 명시되지 않았습니다."

    print("\n✅ 테스트 통과: System Prompt가 순수하게 지침만 포함합니다.")


def test_6_complex_markdown():
    """테스트 6: 복잡한 Markdown 파싱 (다양한 섹션 제목)"""
    print_section("TEST 6: 복잡한 Markdown 파싱")

    md = """# 2025년 상반기 디지털 금융 혁신 보고서

## 핵심 요약 및 시사점

본 보고서는 2025년 상반기 디지털 금융 혁신 동향을 분석한 결과입니다.
AI 기술의 급격한 발전으로 금융 서비스가 재편되고 있습니다.

주요 내용:
- 모바일 뱅킹 사용자 30% 증가
- AI 챗봇 도입률 80% 달성
- 블록체인 기반 서비스 확대

## 사업 추진 배경 및 필요성

### 배경
금융권의 디지털 전환이 가속화되고 있으며, 고객 경험 개선이 필수적입니다.

### 필요성
경쟁력 확보를 위한 디지털 기술 투자가 시급한 상황입니다.

## 세부 분석 내역

### 1. 모바일 뱅킹 현황
전년 대비 40% 성장하며 시장을 주도하고 있습니다.

### 2. AI 기술 적용 사례
대형 은행 10곳이 AI 챗봇을 본격 도입했습니다.

### 3. 오픈뱅킹 생태계
API 연동 서비스가 250여 개로 증가했습니다.

## 향후 추진 방향 및 제언

### 단기 계획 (6개월)
AI 개인화 서비스를 단계적으로 확대합니다.

### 중장기 계획 (1~2년)
블록체인 기술을 활용한 보안 강화를 추진합니다.
"""

    content = parse_markdown_to_content(md)

    print(f"\n[파싱 결과]")
    print(f"\n제목: {content['title']}")
    print(f"\n동적으로 추출된 섹션 제목들:")
    print(f"  요약: '{content['title_summary']}'")
    print(f"  배경: '{content['title_background']}'")
    print(f"  주요내용: '{content['title_main_content']}'")
    print(f"  결론: '{content['title_conclusion']}'")

    print(f"\n섹션 내용 길이:")
    print(f"  요약: {len(content['summary'])} 문자")
    print(f"  배경: {len(content['background'])} 문자")
    print(f"  주요내용: {len(content['main_content'])} 문자")
    print(f"  결론: {len(content['conclusion'])} 문자")

    # 검증
    assert len(content['summary']) > 0, "❌ 요약이 비어있습니다."
    assert len(content['background']) > 0, "❌ 배경이 비어있습니다."
    assert len(content['main_content']) > 0, "❌ 주요내용이 비어있습니다."
    assert len(content['conclusion']) > 0, "❌ 결론이 비어있습니다."

    print("\n✅ 테스트 통과: 복잡한 Markdown도 올바르게 파싱됩니다.")


def run_all_tests():
    """모든 테스트 실행"""
    print("\n")
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 20 + "Prompt 통합 기능 수동 테스트" + " " * 29 + "║")
    print("╚" + "═" * 78 + "╝")

    tests = [
        test_1_topic_context_message,
        test_2_messages_construction,
        test_3_markdown_parsing,
        test_4_english_sections,
        test_5_system_prompt_purity,
        test_6_complex_markdown,
    ]

    passed = 0
    failed = 0

    for i, test_func in enumerate(tests, 1):
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"\n❌ 테스트 실패: {str(e)}")
            failed += 1
        except Exception as e:
            print(f"\n❌ 예외 발생: {str(e)}")
            failed += 1

    # 최종 결과
    print("\n")
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 30 + "테스트 결과" + " " * 36 + "║")
    print("╠" + "═" * 78 + "╣")
    print(f"║  총 테스트: {len(tests)}개" + " " * (69 - len(str(len(tests)))) + "║")
    print(f"║  통과: {passed}개 ✅" + " " * (67 - len(str(passed))) + "║")
    print(f"║  실패: {failed}개 ❌" + " " * (67 - len(str(failed))) + "║")
    print("╚" + "═" * 78 + "╝")

    if failed == 0:
        print("\n🎉 모든 테스트가 성공적으로 통과했습니다!")
    else:
        print(f"\n⚠️  {failed}개의 테스트가 실패했습니다. 로그를 확인해주세요.")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
