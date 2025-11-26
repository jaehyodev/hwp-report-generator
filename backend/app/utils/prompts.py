"""System prompt helpers for report generation and planning."""

import logging
from typing import Optional, Any, List as ListType, Dict as DictType, Iterable

logger = logging.getLogger(__name__)


REPORT_BASE_PROMPT = """당신은 금융 기관의 전문 보고서 작성자입니다.
사용자가 제공하는 주제에 대해 금융 업무보고서를 작성해주세요.

보고서 작성 지침: 
- 각 섹션은 Markdown heading으로 시작하세요
- 마크다운 형식을 엄격히 준수하세요
- 위에 명시된 placeholder와 heading 구조를 정확히 따르세요.(placeholder 임의 추가 금지)
- 각 섹션별 지침을 참고하여 정확하게 작성하세요
- 금융 용어와 데이터를 적절히 활용하여 신뢰성을 높여주세요
- 전문적이고 격식있는 문체로 작성하되, 명확하고 이해하기 쉽게 작성해주세요
- 보고서에 의미 없는 내용이나 중복된 내용을 포함하지 마세요
"""


PLAN_BASE_PROMPT = """당신은 금융 보고서 작성의 전문가입니다.
사용자가 요청한 주제에 대해 체계적이고 구조화된 보고서 계획을 세워주세요.

계획 작성 지침:
- 응답은 반드시 2초 이내 생성 가능하도록 작성(중요)
- 보고서의 제목 결정
- 각 섹션의 제목과 설명 작성
- 각 섹션에서 다룰 주요 포인트 1개 추출

응답 구조 지침(JSON 형식):
{{
    "title": "보고서 제목",
    "sections": [
        {{
            "title": "섹션 제목",
            "description": "섹션 설명 (1문장)",
            "key_points": ["포인트1", "포인트2", "포인트3"],
            "order": 1
        }},
        {{
            "title": "섹션 제목",
            "description": "섹션 설명 (1문장)",
            "key_points": ["포인트1", "포인트2", "포인트3"],
            "order": 2
        }}
    ],
    "estimated_word_count": 5000,
    "estimated_sections_count": 5
}}
"""


DEFAULT_REPORT_RULES = """**기본 보고서 구조 (5개 섹션):**

아래 형식에 맞춰 각 섹션을 작성해주세요:

1. **제목** - 간결하고 명확하게
2. **요약 섹션** - 2-3문단으로 핵심 내용 요약
   - 섹션 제목 예: "요약", "핵심 요약", "Executive Summary" 등
3. **배경 섹션** - 왜 이 보고서가 필요한지 설명
   - 섹션 제목 예: "배경 및 목적", "추진 배경", "사업 배경" 등
4. **주요 내용 섹션** - 구체적이고 상세한 분석 및 설명 (3-5개 소제목 포함)
   - 섹션 제목 예: "주요 내용", "분석 결과", "세부 내역" 등
5. **결론 섹션** - 요약과 향후 조치사항
   - 섹션 제목 예: "결론 및 제언", "향후 계획", "시사점" 등

각 섹션 제목은 보고서 내용과 맥락에 맞게 자유롭게 작성하되,
반드시 위의 4개 섹션(요약, 배경, 주요내용, 결론) 순서를 따라야 합니다.

**출력은 반드시 다음 Markdown 형식을 사용하세요:**
- # {제목} (H1)
- ## {요약 섹션 제목} (H2)
- ## {배경 섹션 제목} (H2)
- ## {주요내용 섹션 제목} (H2)
- ## {결론 섹션 제목} (H2)

**작성 가이드:**
- 각 섹션은 Markdown heading (#, ##)으로 시작하세요
- 위에 명시된 구조를 정확히 따르세요
- 전문적이고 객관적인 톤을 유지하세요""".strip()



def get_base_report_prompt() -> str:
    """보고서 BASE 프롬프트를 반환."""
    return REPORT_BASE_PROMPT


def get_base_plan_prompt() -> str:
    """Sequential Planning BASE 프롬프트를 반환."""
    return PLAN_BASE_PROMPT


def get_default_report_prompt() -> str:
    """기본 보고서 System Prompt (BASE + 기본 규칙) 반환."""
    return _combine_prompts(get_base_report_prompt(), DEFAULT_REPORT_RULES)


def _combine_prompts(base_prompt: str, rules: str) -> str:
    base_prompt = (base_prompt or "").strip()
    rules = (rules or "").strip()
    if base_prompt and rules:
        return f"{base_prompt}\n\n{rules}"
    return base_prompt or rules


def _extract_placeholder_keys(placeholders: Iterable[Any]) -> list[str]:
    keys: list[str] = []
    for item in placeholders:
        key = getattr(item, "placeholder_key", None) or str(item)
        cleaned = key.replace("{{", "").replace("}}", "").strip()
        if cleaned:
            keys.append(cleaned)
    seen = set()
    unique: list[str] = []
    for name in keys:
        if name not in seen:
            seen.add(name)
            unique.append(name)
    return unique


def _build_markdown_rules(placeholders: ListType[str]) -> str:
    markdown_rules = ["**출력은 반드시 다음 Markdown 형식을 사용하세요:**"]
    for index, placeholder in enumerate(placeholders):
        heading = "#" if index == 0 else "##"
        literal = f"{{{{{placeholder}}}}}"
        level = "H1" if index == 0 else "H2"
        markdown_rules.append(f"- {heading} {literal} ({level})")
    return "\n".join(markdown_rules)


def _looks_like_base_prompt(value: Optional[str]) -> bool:
    if not value:
        return False
    normalized = value.strip()
    if not normalized:
        return False
    if "{{" in normalized or "}}" in normalized:
        return False
    return len(normalized) >= 40


def _resolve_template_base(stored: Optional[str]) -> str:
    return stored.strip() if _looks_like_base_prompt(stored) else get_base_report_prompt()


def create_template_specific_rules(
    placeholders: ListType[str],
    metadata: Optional[ListType[DictType[str, Any]]] = None,
) -> str:
    """BASE를 제외한 템플릿 전용 규칙 문자열을 생성."""
    if not placeholders:
        return DEFAULT_REPORT_RULES

    placeholder_list_str = "\n".join([f"- {p}" for p in placeholders])
    markdown_section = _build_markdown_rules([p.replace("{{", "").replace("}}", "") for p in placeholders])
    metadata_section = _format_metadata_sections(placeholders, metadata)

    rules = f"""커스텀 템플릿 구조 (다음 placeholder들을 포함하여 작성):

{placeholder_list_str}

---

출력 마크다운 형식:

{markdown_section}

---

섹션별 상세 지침:

{metadata_section}

"""


    return rules.strip()


def create_dynamic_system_prompt(placeholders: list) -> str:
    """Placeholder 기반 동적 System Prompt 생성 (BASE + 규칙)."""
    keys = _extract_placeholder_keys(placeholders)
    rules = DEFAULT_REPORT_RULES if not keys else create_template_specific_rules([f"{{{{{key}}}}}" for key in keys])
    return _combine_prompts(get_base_report_prompt(), rules)

# ============================================================
# get_system_prompt() - 우선순위 기반 System Prompt 선택
# ============================================================
# 역할: /generate, /ask 등 모든 엔드포인트에서 system prompt를 선택할 때 사용
# 우선순위: custom > template > default

def get_system_prompt(
    custom_prompt: Optional[str] = None,
    template_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> str:
    """
    System Prompt 우선순위에 따라 최종 prompt를 반환합니다.

    우선순위:
    1. custom_prompt (사용자가 직접 입력한 custom system prompt)
    2. template_id 기반 저장된 prompt_system (Template DB 조회)
    3. FINANCIAL_REPORT_SYSTEM_PROMPT (기본값)

    이 함수는 /generate, /ask, /ask_with_follow_up 등
    모든 엔드포인트에서 system prompt를 선택할 때 사용됩니다.

    Args:
        custom_prompt (Optional[str]): 사용자가 직접 입력한 custom system prompt
                                       None이면 무시되고 다음 우선순위로 넘어감
        template_id (Optional[int]): Template ID (DB에서 prompt_system 조회용)
                                      None이면 무시되고 다음 우선순위로 넘어감
        user_id (Optional[int]): 권한 검증용 (template_id가 현재 사용자 소유인지 확인)
                                 template_id가 지정된 경우 필수

    Returns:
        str: 최종 사용할 system prompt 문자열

    Raises:
        ValueError: template_id는 지정되었으나 user_id 누락
        InvalidTemplateError: template_id가 주어졌으나 존재하지 않거나 접근 권한 없음

    Examples:
        >>> # 1. Custom prompt 사용 (최우선)
        >>> prompt = get_system_prompt(
        ...     custom_prompt="당신은 마케팅 전문가입니다."
        ... )
        >>> "마케팅" in prompt
        True

        >>> # 2. Template 기반 prompt 사용
        >>> prompt = get_system_prompt(template_id=1, user_id=42)
        >>> "금융" in prompt  # Template에서 저장된 prompt 사용
        True

        >>> # 3. 기본 prompt 사용 (아무것도 지정 안 함)
        >>> prompt = get_system_prompt()
        >>> "금융 기관" in prompt  # FINANCIAL_REPORT_SYSTEM_PROMPT
        True
    """
    from app.database.template_db import TemplateDB, PlaceholderDB
    from app.utils.response_helper import ErrorCode

    if custom_prompt:
        logger.info(f"Using custom system prompt - length={len(custom_prompt)}")
        return custom_prompt

    if template_id:
        if not user_id:
            raise ValueError("user_id is required when template_id is specified")

        logger.info(f"Fetching template - template_id={template_id}, user_id={user_id}")

        try:
            template = TemplateDB.get_template_by_id(template_id, user_id)
            if not template:
                logger.warning(
                    f"Template not found - template_id={template_id}, user_id={user_id}"
                )
                from app.utils.exceptions import InvalidTemplateError

                raise InvalidTemplateError(
                    code=ErrorCode.TEMPLATE_NOT_FOUND,
                    http_status=404,
                    message=f"Template #{template_id}을(를) 찾을 수 없습니다.",
                    hint="존재하는 template_id를 확인하거나 template_id 없이 요청해주세요."
                )

            base_prompt = _resolve_template_base(template.prompt_user)
            if template.prompt_system:
                logger.info(
                    f"Using stored template prompt_system - template_id={template_id}, length={len(template.prompt_system)}"
                )
                return _combine_prompts(base_prompt, template.prompt_system)

            # Legacy fallback - regenerate rules from placeholders
            placeholders = PlaceholderDB.get_placeholders_by_template(template_id)
            if placeholders:
                logger.warning(
                    "Template prompt_system missing; regenerating from placeholders - "
                    f"template_id={template_id}"
                )
                rules = create_template_specific_rules([f"{{{{{key}}}}}" for key in _extract_placeholder_keys(placeholders)])
                return _combine_prompts(base_prompt, rules)

            logger.warning(
                "Template has no prompt_system or placeholders; using default base prompt - "
                f"template_id={template_id}"
            )
            return base_prompt

        except Exception as e:
            logger.error(f"Error fetching template - template_id={template_id}, error={str(e)}")
            raise

    logger.info("Using default report system prompt")
    return get_default_report_prompt()


# ============================================================
# Step 4: create_system_prompt_with_metadata() - 메타정보 통합 Prompt 생성
# ============================================================
# 역할: Placeholder + Claude 생성 메타정보를 통합한 System Prompt 생성
# 사용 시점: Template 업로드 시 (claude_metadata_generator로 생성된 메타정보 포함)

def create_system_prompt_with_metadata(
    placeholders: ListType[str],
    metadata: Optional[ListType[DictType[str, Any]]] = None,
) -> str:
    """메타정보를 통합한 BASE + 규칙 구조의 System Prompt 생성."""
    if not placeholders:
        logger.info("[PROMPT] No placeholders provided, returning default")
        return get_default_report_prompt()

    rules = create_template_specific_rules(placeholders, metadata)
    prompt = _combine_prompts(get_base_report_prompt(), rules)
    logger.info(
        f"[PROMPT] System prompt created with metadata - placeholders={len(placeholders)}, "
        f"metadata={'yes' if metadata else 'no'}, prompt_length={len(prompt)}"
    )
    return prompt


def _format_metadata_sections(
    placeholders: ListType[str],
    metadata: Optional[ListType[DictType[str, Any]]] = None,
) -> str:
    """
    메타정보 섹션 포매팅.

    각 Placeholder에 대한 메타정보를 읽기 좋은 형식으로 정렬합니다.
    """
    if not metadata:
        return "(메타정보 미생성 - 기본 지침을 참고하세요)"

    # 메타정보를 key로 인덱싱하여 빠르게 조회
    metadata_map = {item.get("key"): item for item in metadata}

    sections = []
    for placeholder in placeholders:
        item = metadata_map.get(placeholder)

        if not item:
            # 메타정보 없는 Placeholder는 건너뛰기
            logger.warning(
                f"[PROMPT] Metadata not found for placeholder: {placeholder}"
            )
            sections.append(f"### {placeholder}\n(메타정보 미생성)")
            continue

        display_name = item.get("display_name", "N/A")
        description = item.get("description", "N/A")
        examples = item.get("examples", [])
        required = item.get("required", False)

        # 예시 포매팅
        examples_str = _format_examples(examples)

        # 섹션 구성
        section = f"""### {placeholder} ({display_name})

**설명:** {description}

**예시:**
{examples_str}

**필수 여부:** {'필수' if required else '선택'}"""

        sections.append(section)

    return "\n\n".join(sections)


def _format_examples(examples: Optional[ListType[str]]) -> str:
    """예시 포매팅."""
    if not examples or len(examples) == 0:
        return "- (예시 미제공)"
    return "\n".join([f"- {ex}" for ex in examples])


def create_topic_context_message(topic_input_prompt: str) -> dict:
    """대화 주제를 포함하는 context message를 생성합니다.

    이 함수는 Topics API의 MessageAsk 엔드포인트에서 사용되며,
    대화의 주제를 첫 번째 user message로 추가하여
    Claude가 일관된 맥락을 유지하도록 돕습니다.

    Args:
        topic_input_prompt: 대화 주제 (예: "2025 디지털뱅킹 트렌드 분석")

    Returns:
        Claude API messages 형식의 딕셔너리
        {
            "role": "user",
            "content": "대화 주제: {topic}\\n\\n이전 메시지를 참고하세요."
        }

    Examples:
        >>> msg = create_topic_context_message("디지털뱅킹 트렌드")
        >>> msg["role"]
        'user'
        >>> "디지털뱅킹 트렌드" in msg["content"]
        True
    """
    return {
        "role": "user",
        "content": f"**대화 주제**: {topic_input_prompt}\n\n이전 메시지들을 문맥으로 활용하여 일관된 문체와 구조로 답변하세요."
    }
