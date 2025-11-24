"""System prompt helpers for report generation and planning."""

import logging
from typing import Optional, Any, List as ListType, Dict as DictType, Iterable

logger = logging.getLogger(__name__)


REPORT_BASE_PROMPT = """당신은 금융 기관의 전문 보고서 작성자입니다.
사용자가 제공하는 주제에 대해 **Markdown 형식의 금융 업무보고서**를 작성합니다.

이 보고서는 **아래 모든 규칙을 절대적으로 준수하여 작성**해야 합니다.

---

## **Markdown 절대 규칙**

1. `#`(H1)은 **보고서 전체에서 단 1회만 사용**한다.
2. 모든 `##`(H2)는 **반드시 번호 + 마침표 + 제목**의 형태로 작성한다.

   * 예시: `##1. 제목`, `##2. 내용`
3. H2 제목은 **13자 이하**로 작성한다.

   * placeholder 내용이 길 경우, 반드시 13자 이하로 **자동 요약하여 제목으로 사용**한다.
4. 인용( `>` )은 **한 단계만 사용**하며, **중첩 금지**다.
5. unordered list(`-`)와 ordered list(`1.`)는 모두 **최대 2단계까지만 사용**한다.
6. 다음 요소는 **절대 사용하지 않는다:**

   * Table
   * Code block
   * Checkbox
   * Link(URL 포함 모든 형태)
   * Image
   * Border(테두리 강조 블록)
7. 아래 템플릿 외의 Markdown heading 은 **추가하지 않는다.**
8. 아래 “섹션별 상세 지침”은 설명용이며 **출력에 포함하지 않는다.**
9. `###`(H3)은 절대 사용하지 않고 ordered list(`1.`)로 대처한다.
10. 이모티콘을 사용하지 않는다.

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


ADVANCED_PLANNER_PROMPT = """당신은 **고급 프롬프트 엔지니어이자 도메인 역할 설계자(Role Planner)**입니다.
내 요청을 분석하고, 다음 두 가지를 수행하세요:

---

## 1. **보고서 작성에 가장 적합한 전문가 역할을 자동 선택하세요.**

내가 제공한 주제를 분석한 뒤, 아래 중 하나 이상의 역할을 선택합니다:

* 금융 분석가 (Financial Analyst)
* 조직 심리학자 (Organizational Psychologist)
* 기술 아키텍트 (Technical Architect)
* 마케팅 전략가 (Marketing Strategist)
* 정책 연구자 (Policy Researcher)
* 경영 컨설턴트 (Management Consultant)
* 위험관리 전문가 (Risk Specialist)
* 데이터 분석가 (Data Analyst)
* 기타: 주제에 더 적합한 역할이 있을 경우 스스로 정의해도 됩니다.

**역할 선택 기준**

* 주제의 성격(기술/조직/경영/금융/마케팅/사회적 이슈 등)
* 보고서가 다루게 될 주요 이해관계자
* 해결해야 할 문제의 본질
* 필요한 분석 관점과 전문 지식

---

## 2. 선택된 역할이 사용할 **전문적 분석 프레임워크·시각·문체·용어 체계**를 설정하세요.

예:

* 금융 분석가 → Top-down Macro Analysis, 미시 지표, 리스크 인사이트, 공식 보고 문체
* 기술 아키텍트 → 시스템 구조화, 문제 재정의, 계층 아키텍처, 도식적 사고
* 조직 심리학자 → BPS Model, 동기/행동 패턴 분석, 근거 중심 접근
* 마케팅 전략가 → STP, AARRR, 포지셔닝, 카피라이팅 톤

---

## 3. **아래 7개 섹션으로 이루어진 상세 보고서 계획을 JSON으로 생성하세요.**

각 섹션은 **계획(Plan)**이며, 선택된 역할의 관점과 프레임워크가 반영되어야 합니다.

**각 섹션의 의미:**

* **TITLE**: 보고서 전체를 대표하는 제목 (13자 이하 권장)
* **DATE**: 발행 날짜 (예시: 2025.11.24)
* **BACKGROUND**: 보고서가 생성되는 맥락, 문제 정의, 이슈 상황, 필요성
* **MAIN_CONTENT**: 전문가 역할이 적용될 분석 프레임워크 기반의 상세 계획 (3-5개 서브항목 예상)
* **SUMMARY**: 전체 계획을 2~3문단으로 압축한 실행 요약
* **CONCLUSION**: 전략적 제언, 의사결정 관점, 다음 단계 제안
* **SYSTEM**: 선택된 역할, 적용 프레임워크, 문체 원칙, 분석 기준 등 내부 지침

---

## 4. **JSON 응답 형식 규칙 (필수)**

아래 JSON 구조로 응답하세요. Markdown 형식은 불가:

```json
{
  "title": "보고서 제목",
  "selected_role": "선택된 전문가 역할명 (예: Financial Analyst)",
  "framework": "적용된 주요 분석 프레임워크 (예: Top-down Macro Analysis)",
  "sections": [
    {
      "title": "배경 분석",
      "description": "BACKGROUND 섹션 핵심 설명 (1-2문장)",
      "key_points": ["포인트1", "포인트2"],
      "order": 1
    },
    ... (more sections)
  ],
  "estimated_word_count": 5000,
  "estimated_sections_count": 5
}
```

**주의사항:**
* 응답은 반드시 유효한 JSON만 포함
* Markdown 형식, 설명문, 추가 텍스트 불가
* 마크다운 코드블록(```)도 불가

---

## 5. **주제 입력 (사용자 지정)**

요청 주제: {{USER_TOPIC}}

위 주제에 대해 Role Planner 패턴을 적용하여 상기 JSON 형식으로 응답하세요.
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


def get_advanced_planner_prompt() -> str:
    """고급 Role Planner 프롬프트를 반환.

    Role Planner 패턴을 적용하여 주제에 맞는 전문가 역할을 자동 선택하고,
    해당 역할의 분석 프레임워크를 기반으로 상세 보고서 계획을 생성합니다.

    Returns:
        str: ADVANCED_PLANNER_PROMPT 상수 (JSON 형식 응답 요구)

    Examples:
        >>> prompt = get_advanced_planner_prompt()
        >>> "Role Planner" in prompt
        True
        >>> "{{USER_TOPIC}}" in prompt
        True
    """
    return ADVANCED_PLANNER_PROMPT


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
    cleaned = []
    for placeholder in placeholders:
        if not placeholder:
            continue
        stripped = placeholder.strip()
        if not stripped:
            continue
        normalized = stripped.replace("{{", "").replace("}}", "").strip()
        if not normalized:
            continue
        cleaned.append(normalized)
    if not cleaned:
        return ""

    sections: list[str] = []
    for index, name in enumerate(cleaned):
        literal = f"{{{{{name}}}}}"
        if index == 0:
            sections.append(f"# {literal}")
            sections.append("")
            continue

        sections.append(f"##{index}. {literal}")
        sections.append("(본문)")
        sections.append("")

    while sections and sections[-1] == "":
        sections.pop()

    markdown_rules = ["**출력 템플릿 구조(엄격히 준수)** ","보고서는 아래 구조와 순서로 작성한다:"
                      , "```", *sections, "```" 
                      ,"※ 각 {{placeholder}}는 출력 시 **의미에 맞는 실제 보고서 내용으로 대체**됨."
                      ," ※ H2 제목은 항상 **13자 이하로 변환된 제목 문구**로 표현해야 한다."]
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

# 기본 금융 보고서 시스템 프롬프트
FINANCIAL_REPORT_SYSTEM_PROMPT = get_default_report_prompt()

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


TITLE_GROUP_KEYS = {
    "TITLE_BACKGROUND",
    "TITLE_MAIN_CONTENT",
    "TITLE_SUMARY",
    "TITLE_CONCLUSION",
}

PLACEHOLDER_DESCRIPTIONS: DictType[str, str] = {
    "TITLE": "보고서 전체 제목.",
    "BACKGROUND": "보고서 배경, 문제 맥락, 시장 환경 설명.",
    "MAIN_CONTENT": "핵심 분석 내용, 주요 지표, 발견사항.",
    "SUMARY": "전체 내용을 2~3문단으로 압축한 요약.",
    "CONCLUSION": "최종 결론, 전망, 전략적 제언.",
    "TITLE_GROUP": "섹션 제목으로 사용되는 짧은 문구. (반드시 13자 이하)",
    "DATE": "보고서 작성 또는 발행 날짜.",
}

# SUMMARY 철자를 사용하는 템플릿도 지원
PLACEHOLDER_DESCRIPTIONS["SUMMARY"] = PLACEHOLDER_DESCRIPTIONS["SUMARY"]


def _normalize_placeholder_key(placeholder: str) -> str:
    """Placeholder 문자열을 {{ }} 제거 후 비교 가능한 키로 정규화."""
    return placeholder.replace("{{", "").replace("}}", "").strip().upper()


def _format_metadata_sections(
    placeholders: ListType[str],
    metadata: Optional[ListType[DictType[str, Any]]] = None,
) -> str:
    """메타정보 섹션 포매팅 (placeholder 순서를 보존)."""
    if not placeholders:
        return "(메타정보 미생성 - 기본 지침을 참고하세요)"

    metadata_map: DictType[str, DictType[str, Any]] = {}
    for item in metadata or []:
        raw_key = str(item.get("key", "")).strip()
        normalized_key = _normalize_placeholder_key(raw_key) if raw_key else ""
        if raw_key:
            metadata_map[raw_key] = item
        if normalized_key and normalized_key not in metadata_map:
            metadata_map[normalized_key] = item

    sections: list[str] = []
    processed_keys: set[str] = set()
    title_group_printed = False

    def _get_description(key: str, placeholder: str) -> str:
        desc = PLACEHOLDER_DESCRIPTIONS.get(key)
        if desc:
            return desc
        metadata_item = metadata_map.get(placeholder) or metadata_map.get(key)
        if metadata_item:
            meta_desc = metadata_item.get("description")
            if meta_desc:
                return meta_desc
        return "해당 섹션에 필요한 내용을 간결히 요약하세요."

    for idx, placeholder in enumerate(placeholders):
        normalized_key = _normalize_placeholder_key(placeholder)
        if not normalized_key or normalized_key in processed_keys:
            continue

        if normalized_key in TITLE_GROUP_KEYS:
            if title_group_printed:
                continue
            grouped_placeholders: list[str] = []
            seen_group_keys: set[str] = set()
            for item in placeholders[idx:]:
                group_key = _normalize_placeholder_key(item)
                if group_key in TITLE_GROUP_KEYS and group_key not in seen_group_keys:
                    grouped_placeholders.append(item)
                    seen_group_keys.add(group_key)
            if not grouped_placeholders:
                continue
            placeholder_text = ", ".join(grouped_placeholders)
            sections.append(
                f"* **{placeholder_text}**\n  {_get_description('TITLE_GROUP', placeholder)}"
            )
            processed_keys.update(seen_group_keys)
            title_group_printed = True
            continue

        sections.append(f"* **{placeholder}**\n  {_get_description(normalized_key, placeholder)}")
        processed_keys.add(normalized_key)

    if not sections:
        return "(메타정보 미생성 - 기본 지침을 참고하세요)"

    return "\n".join(sections)


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
