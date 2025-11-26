"""
Prompt 통합 검증 스크립트

이 스크립트는 prompt 통합이 올바르게 완료되었는지 자동으로 검증합니다.
- 하드코딩된 prompt가 남아있지 않은지 확인
- 올바른 import가 추가되었는지 확인
- 파일 구조가 계획대로 생성되었는지 확인

실행 방법:
    cd backend
    uv run python tests/verify_prompt_integration.py
"""
import sys
import os
from pathlib import Path
import re

# 프로젝트 루트
project_root = Path(__file__).parent.parent.parent
backend_root = project_root / "backend"


def print_header(title):
    """헤더 출력"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def check_file_exists(filepath, description):
    """파일 존재 확인"""
    full_path = backend_root / filepath
    exists = full_path.exists()
    status = "✅" if exists else "❌"
    print(f"{status} {description}: {filepath}")
    return exists


def check_hardcoded_prompts():
    """하드코딩된 prompt 확인"""
    print_header("1. 하드코딩된 Prompt 제거 확인")

    search_text = "당신은 금융 기관의 전문 보고서 작성자입니다"
    files_to_check = [
        "app/utils/claude_client.py",
        "app/routers/topics.py",
        "app/main.py"
    ]

    found_hardcoded = []

    for filepath in files_to_check:
        full_path = backend_root / filepath
        if not full_path.exists():
            print(f"⚠️  파일 없음: {filepath}")
            continue

        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if search_text in content:
            # utils/prompts.py는 예외
            if "prompts.py" not in filepath:
                found_hardcoded.append(filepath)
                print(f"❌ 하드코딩된 prompt 발견: {filepath}")
            else:
                print(f"✅ {filepath} (정상 - prompt 정의 파일)")
        else:
            print(f"✅ {filepath} - 하드코딩 없음")

    if found_hardcoded:
        print(f"\n❌ {len(found_hardcoded)}개 파일에 하드코딩된 prompt가 남아있습니다.")
        return False
    else:
        print("\n✅ 하드코딩된 prompt가 모두 제거되었습니다.")
        return True


def check_imports():
    """Import 확인"""
    print_header("2. Import 확인")

    checks = [
        {
            "file": "app/utils/claude_client.py",
            "import": "from app.utils.prompts import get_default_report_prompt",
            "description": "claude_client.py의 prompts import"
        },
        {
            "file": "app/routers/topics.py",
            "import": "from app.utils.prompts import",
            "description": "topics.py의 prompts import"
        },
        {
            "file": "app/routers/topics.py",
            "import": "from app.utils.markdown_parser import parse_markdown_to_content",
            "description": "topics.py의 markdown_parser import"
        },
        {
            "file": "app/main.py",
            "import": "from app.utils.markdown_parser import parse_markdown_to_content",
            "description": "main.py의 markdown_parser import"
        }
    ]

    all_passed = True

    for check in checks:
        full_path = backend_root / check["file"]
        if not full_path.exists():
            print(f"⚠️  파일 없음: {check['file']}")
            all_passed = False
            continue

        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if check["import"] in content:
            print(f"✅ {check['description']}")
        else:
            print(f"❌ {check['description']} - import 누락")
            all_passed = False

    if all_passed:
        print("\n✅ 모든 import가 올바르게 추가되었습니다.")
    else:
        print("\n❌ 일부 import가 누락되었습니다.")

    return all_passed


def check_file_structure():
    """파일 구조 확인"""
    print_header("3. 파일 구조 확인")

    files = [
        ("app/utils/prompts.py", "✨ 새로 생성"),
        ("app/utils/claude_client.py", "🔧 수정됨"),
        ("app/utils/markdown_parser.py", "🔧 전체 교체"),
        ("app/routers/topics.py", "🔧 수정됨"),
        ("app/main.py", "🔧 수정됨"),
    ]

    all_exist = True

    for filepath, status in files:
        exists = check_file_exists(filepath, status)
        if not exists:
            all_exist = False

    if all_exist:
        print("\n✅ 모든 파일이 존재합니다.")
    else:
        print("\n❌ 일부 파일이 누락되었습니다.")

    return all_exist


def check_markdown_parser_functions():
    """markdown_parser.py의 함수들 확인"""
    print_header("4. Markdown Parser 함수 확인")

    filepath = backend_root / "app/utils/markdown_parser.py"
    if not filepath.exists():
        print("❌ markdown_parser.py 파일이 없습니다.")
        return False

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    required_functions = [
        "parse_markdown_to_content",
        "extract_all_h2_sections",
        "classify_section",
        "extract_title_from_markdown"
    ]

    all_found = True

    for func_name in required_functions:
        pattern = rf"def {func_name}\("
        if re.search(pattern, content):
            print(f"✅ {func_name}() 함수 존재")
        else:
            print(f"❌ {func_name}() 함수 누락")
            all_found = False

    if all_found:
        print("\n✅ 모든 필수 함수가 존재합니다.")
    else:
        print("\n❌ 일부 함수가 누락되었습니다.")

    return all_found


def check_prompts_module():
    """prompts.py 모듈 확인"""
    print_header("5. Prompts 모듈 확인")

    filepath = backend_root / "app/utils/prompts.py"
    if not filepath.exists():
        print("❌ prompts.py 파일이 없습니다.")
        return False

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    checks = [
        ("def get_base_report_prompt", "BASE 프롬프트 getter"),
        ("def get_default_report_prompt", "기본 프롬프트 조합"),
        ("create_template_specific_rules", "규칙 생성 함수"),
        ("create_topic_context_message", "Topic context 함수 정의"),
    ]

    all_found = True

    for item, description in checks:
        if item in content:
            print(f"✅ {description}: '{item}'")
        else:
            print(f"❌ {description} 누락: '{item}'")
            all_found = False

    if all_found:
        print("\n✅ prompts.py가 올바르게 구성되었습니다.")
    else:
        print("\n❌ prompts.py 구성이 불완전합니다.")

    return all_found


def check_claude_client_changes():
    """claude_client.py 변경사항 확인"""
    print_header("6. Claude Client 변경사항 확인")

    filepath = backend_root / "app/utils/claude_client.py"
    if not filepath.exists():
        print("❌ claude_client.py 파일이 없습니다.")
        return False

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    checks = [
        ("from app.utils.prompts import get_default_report_prompt", "Import 추가"),
        ("def generate_report(self, topic: str,", "generate_report 시그니처"),
        ('"system": get_default_report_prompt()', "system prompt 사용"),
    ]

    all_found = True

    for item, description in checks:
        if item in content:
            print(f"✅ {description}")
        else:
            print(f"❌ {description} 누락")
            all_found = False

    # _parse_report_content 메서드가 제거되었는지 확인
    if "_parse_report_content" in content:
        print(f"❌ _parse_report_content() 메서드가 제거되지 않았습니다.")
        all_found = False
    else:
        print(f"✅ _parse_report_content() 메서드 제거됨")

    if all_found:
        print("\n✅ claude_client.py가 올바르게 수정되었습니다.")
    else:
        print("\n❌ claude_client.py 수정이 불완전합니다.")

    return all_found


def check_topics_router_changes():
    """topics.py 변경사항 확인"""
    print_header("7. Topics Router 변경사항 확인")

    filepath = backend_root / "app/routers/topics.py"
    if not filepath.exists():
        print("❌ topics.py 파일이 없습니다.")
        return False

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    checks = [
        ("from app.utils.prompts import", "prompts import"),
        ("create_topic_context_message", "create_topic_context_message import"),
        ("get_system_prompt", "System prompt helper 사용"),
        ("parse_markdown_to_content", "markdown_parser import"),
        ("topic_context_msg = create_topic_context_message", "Topic context message 생성"),
        ("claude_messages = [topic_context_msg] + claude_messages", "Topic context를 첫 메시지로 추가"),
    ]

    all_found = True

    for item, description in checks:
        if item in content:
            print(f"✅ {description}")
        else:
            print(f"❌ {description} 누락")
            all_found = False

    if all_found:
        print("\n✅ topics.py가 올바르게 수정되었습니다.")
    else:
        print("\n❌ topics.py 수정이 불완전합니다.")

    return all_found


def run_verification():
    """전체 검증 실행"""
    print("\n")
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 25 + "Prompt 통합 검증" + " " * 36 + "║")
    print("╚" + "═" * 78 + "╝")

    results = {
        "하드코딩 제거": check_hardcoded_prompts(),
        "Import 확인": check_imports(),
        "파일 구조": check_file_structure(),
        "Markdown Parser": check_markdown_parser_functions(),
        "Prompts 모듈": check_prompts_module(),
        "Claude Client": check_claude_client_changes(),
        "Topics Router": check_topics_router_changes(),
    }

    # 최종 결과
    print_header("검증 결과 요약")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = "✅ 통과" if result else "❌ 실패"
        print(f"{status} - {name}")

    print("\n" + "-" * 80)
    print(f"\n총 {total}개 항목 중 {passed}개 통과")

    if passed == total:
        print("\n🎉 모든 검증 항목을 통과했습니다!")
        print("Prompt 통합이 성공적으로 완료되었습니다.")
    else:
        failed = total - passed
        print(f"\n⚠️  {failed}개 항목이 실패했습니다.")
        print("위의 로그를 확인하여 누락된 부분을 수정해주세요.")

    return passed == total


if __name__ == "__main__":
    success = run_verification()
    sys.exit(0 if success else 1)
