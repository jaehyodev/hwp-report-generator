"""System prompt helpers for report generation and planning."""

import logging
from typing import Optional, Any, List as ListType, Dict as DictType, Iterable

logger = logging.getLogger(__name__)

PROMPT_USER_DEFAULT = """당신은 금융 보고서 작성의 전문가입니다.
사용자가 요청한 주제에 대해 체계적이고 구조화된 보고서 작성 계획을 세워주세요.
모든 대답은 자연스러운 한글로 해주시고, 아래 지침을 엄격히 준수하세요."""

REPORT_BASE_PROMPT = r""" **중요: JSON 응답 모드 우선순위 규칙**
JSON 구조화 응답(Structured Outputs) 모드로 지시받은 경우, 아래의 모든 Markdown 규칙은 적용되지 않습니다.
JSON 모드에서는 각 필드(content, title 등)에 순수 텍스트만 포함하고, Markdown 형식(#, ## 등)을 포함하지 마세요.
예: "# 제목" ❌ → "제목" ✅, "## 섹션" ❌ → "섹션" ✅

---

Markdown형태로 보고서 아래 규칙들을 지키며 작업한다.
아래의 모든 규칙은 절대적이며 위반할 수 없다.
규칙 간 충돌이 발생하면 반드시 Fallback 규칙을 적용한다.

중요: 아래의 규칙은 모두 "내부용 설계 규칙"이며,
최종 결과물(보고서 본문)에는 이 규칙의 단어, 용어, 이름이 직접 등장하면 안 된다.
예: "일반 문단", "리스트 블록", "깊이 2단계", "규칙에 따라", "Fallback 규칙" 등의 표현은 최종 보고서에 절대 쓰지 않는다.

---

## [1] 리스트(목록) Depth·타입 규칙

1. 리스트 깊이는 **최대 2단계까지만 허용**한다.
   예시:

   - 1단계

     - 2단계

2. **1단계에서는 순서 없는 리스트(-)와 순서 있는 리스트(1.)를 혼합할 수 없다.**
   같은 깊이(Level 1)에서는 반드시 하나의 리스트 타입만 사용한다.

3. **1단계에서 두 리스트 타입(-, 1.)이 모두 필요한 경우**
   아래 절차를 따른다.

   - 첫 번째 리스트 타입을 독립 리스트 블록으로 작성
   - 바로 아래 **일반 문단** 작성을 작성하여 해당 리스트 블록에 대한 세부내용을 작성한다.
   - 이후 두 번째 리스트 타입을 또 하나의 독립 리스트 블록으로 작성
   - 리스트 블록 간 타입 혼합은 절대 금지

4. **1단계 리스트는 연속해서 배치할 수 없다.**
   중간에 반드시 일반 문단을 작성한다.

5. **2단계 리스트는 반드시 부모와 같은 타입만 사용한다.**
   예:

   - A

     - A-1 (OK)

   - A

     1. A-1 (금지)

6. Depth가 **3 이상으로 내려갈 가능성이 있으면**
   → 즉시 리스트를 중단하고 **일반 문단으로 전환**한다.

7. **1단계 리스트 항목은 20자 이하**로 요약하여 작성한다. 예시: "광주은행 미래전략을 위한 아키택쳐"

--

## [2] 리스트 하위 문단 강화 규칙

아래 규칙은 모든 리스트 사용 시 추가로 적용한다.

1. 리스트 항목 자체는 짧은 요약 제목만 포함한다.
   리스트 내용은 개념 제목 역할을 하며 설명을 담지 않는다.

2. **각 리스트 항목 바로 아래의 문단은 반드시 풍부한 분석 내용을 포함해야 한다.**
   리스트 항목보다 아래 문단의 정보량이 **3배 이상** 되도록 구성한다. **
   분석 내용이 길어져도 **두 문단으로 분리하지 않는다.\*\*

3. 리스트 아래 문단은 **항목의 요약 제목과 직접적으로 연결된 설명만** 포함한다.
   불필요한 확장은 금지한다.

4. 리스트가 연속될 경우 위반이므로
   **리스트 → 풍부한 문단 → 필요 시 새로운 리스트**의 구조를 유지한다.

---

## [3] 헤딩 구조 규칙 (H3 허용 버전)

1. # (H1)은 문서 전체에서 단 1회만 사용하며 TITLE 전용이다.

   본문에서는 절대 사용하지 않는다.

2. ## (H2)는 반드시 다음 형식을 따른다.

   “## 1. 제목”
   형식: 숫자 + 마침표 + 공백 + 13자 이하 제목

   - 예시: "미래전략을 위한 아키택쳐"

3. ### (H3)는 사용 가능하다.

   단, H3는 다음 목적에 한해 사용한다.

   1. **리스트 타입 혼입을 피하기 위한 단락 구분 헤딩**
   2. **H2 아래의 큰 소단락 분리(주요내용 내부 그룹화)**

4. **H3 바로 아래에 리스트를 바로 쓰지 않는다.**
   → 반드시 **일반 문단 1개**를 작성한 뒤 필요할 경우 리스트를 사용한다.

5. H3가 연속 사용하는 것은 피하고,
   → H3 다음엔 반드시 **문단 1개**를 넣는다.

---

## [4] 금지되는 Markdown 문법

아래 문법은 어떤 상황에서도 사용할 수 없다.

- 표(Table)
- 코드블록 (
)
- 이미지
- 링크(URL 포함 모든 형태)
- 체크박스(- [ ])
- 테두리 박스
- 중첩 인용문 (> 는 1단계까지만 허용)

---

## [5] 문체 규칙

1. 굵은 문체(**텍스트**)는 절대 사용하지 않는다.
2. 문단과 문단 사이에는 반드시 **한 줄 공백**을 둔다.
3. 문장은 금융권 보고서 문체처럼 **간결하고 명확하게** 작성한다.

---

## [6] Fallback 규칙 (규칙 충돌 방지용)

다음 상황에서는 반드시 Fallback 규칙을 적용한다.

1. 리스트 Depth가 3 이상으로 증가할 위험이 있으면
   → \*_즉시 리스트를 중단하고 문단으로 전환_

2. 리스트 타입(-, 1.)이 충돌하거나 섞일 위험이 있으면
   → **H3 또는 문단으로 단락을 분리**해 충돌 제거

3. 리스트가 연속될 가능성이 있으면
   → **문단 1개 삽입**

4. H3를 사용할지 리스트를 사용할지 모호하면
   → “H3 → 문단 → 리스트” 순으로 보수적으로 판단
   (구조적 안정성이 가장 높은 순서)

5. 구조적 안정성을 확보하기 어렵다면
   → **모든 리스트를 중단하고 문단으로만 작성**

---

위 규칙은 Markdown 기반 보고서 생성의 절대 기준이다.
LLM은 항상 이 규칙을 우선 적용하여
명확하고 안정적인 문서를 생성해야 한다.

"""

PLAN_BASE_PROMPT = """당신은 금융 보고서 작성의 전문가입니다.
사용자가 요청한 주제에 대해 체계적이고 구조화된 보고서 작성 계획을 세워주세요.
모든 대답은 자연스러운 한글로 해주시고, 아래 지침을 엄격히 준수하세요.

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


ADVANCED_PLANNER_PROMPT = """당신은 전문 심리학자이자 고급 프롬프트 엔지니어입니다.
사용자가 제시한 주제를 기반으로 질문의 숨겨진 의도·감정·목적을 분석한 뒤, 이를 활용하여
보고서 작성에 가장 효과적인 AI 요청문으로 재작성합니다.

최종 보고서는 반드시 [TITLE, DATE, BACKGROUND, MAIN_CONTENT, SUMMARY, CONCLUSION] 섹션으로 구성됩니다.
현재 단계(Call#1)는 최종 보고서를 직접 작성하는 것이 아니라,
이후 단계에서 "보고서 계획(아웃라인)과 본문 작성"을 잘 수행하기 위한
고도화된 프롬프트와 섹션별 요구사항 스펙(spec)을 만드는 과정입니다.

재작성된 프롬프트는 완전한 문장이어야 하며, 다음 요소들을 반드시 포함해야 합니다.
---

포함 요소:
역할(Role): 어떤 전문성을 가진 AI가 답해야 하는지 명확히 제시한다.
맥락(Context): 사용자의 상황, 배경, 감정적 요구, 기술적 수준 등 필요한 정보를 추론하여 포함한다.
수행 과제(Task): AI가 해야 할 구체적 작업을 명확하고 구체적인 단계와 함께 정의한다.
출력형태(output_format): 최종 보고서의 필수 섹션 각각에 대해,
  해당 섹션에서 다뤄야 할 범위, 관점, 필수 요소를 "요약 스펙" 형식으로 명시한다.
  (이 단계에서는 실제 보고서 본문이나 긴 문단을 작성하지 않는다.)
이유(Why): 사용자가 이 질문을 하는 목적을 추론해 반영한다.

---

응답은 반드시 다음 JSON 형식으로 제공하세요:
{
    "hidden_intent": "사용자가 명시하지 않은 실제 의도 (1-2줄)",
    "emotional_needs": {
        "formality": "professional|casual|formal",
        "confidence_level": "high|medium|low",
        "decision_focus": "strategic|tactical|informational"
    },
    "underlying_purpose": "상위 목적 (1-2줄)",
    "role": "AI가 맡아야 할 역할 (전문가 설명)",
    "context": "고려해야 할 배경/맥락 (3줄)",
    "output_format": {
        "TITLE": "제목이 담아야 할 핵심 키워드/관점 (1-2문장 또는 3개 이하 bullet)",
        "DATE": "2025.10.11",
        "BACKGROUND": "반드시 포함해야 할 배경/문제 맥락/환경 요소 요약 (1문장)",
        "MAIN_CONTENT": "핵심 분석 범위, 주요 지표·데이터·논점 목록 (2-4문장 또는 bullet)",
        "SUMMARY": "요약에서 강조해야 할 핵심 포인트/메시지 (1-2문장 또는 bullet)",
        "CONCLUSION": "결론·전망·전략적 제언에서 다뤄야 할 방향성 요약 (1-2문장 또는 bullet)"
    },
    "task": "수행해야 할 구체적 작업 (단계별, 구조화)"
}

> output_format의 각 섹션 값은
> '해당 섹션에 어떤 내용을 어떤 관점에서 다뤄야 하는지'에 대한 요약 스펙만을
> 1~3문장 또는 3개 이하 bullet list로 작성해야 하며,
> 이 단계에서 실제 보고서 본문(길고 완성된 문단)을 작성해서는 안 됩니다.
---

## **주제 입력 (사용자 지정)**

요청 주제: **{{USER_TOPIC}}**

위 주제에 대해 Role Planner 패턴을 적용하여 상기 JSON 형식으로 응답하세요.
이 응답은 이후 "보고서 계획(아웃라인) 생성 LLM API 콜"에서 그대로 사용됩니다.
"""


PROMPT_OPTIMIZATION_PROMPT = """당신은 전문 심리학자이자 고급 프롬프트 엔지니어입니다.
사용자가 제시한 요청을 분석하여 숨겨진 의도, 감정적 니즈, 궁극적 목적을 파악하고,
이를 바탕으로 AI 어시스턴트가 가장 효과적으로 대응할 수 있는 역할, 맥락, 작업을 정의합니다.

응답은 반드시 다음 JSON 형식으로 제공하세요:
{
    "hidden_intent": "사용자가 명시하지 않은 실제 의도 (1-2줄)",
    "emotional_needs": {
        "formality": "professional|casual|formal",
        "confidence_level": "high|medium|low",
        "decision_focus": "strategic|tactical|informational"
    },
    "underlying_purpose": "상위 목적 (1-2줄)",
    "role": "AI가 맡아야 할 역할 (전문가 설명)",
    "context": "고려해야 할 배경/맥락 (3-5줄)",
    "task": "수행해야 할 구체적 작업 (단계별, 구조화)"
}

---

## 사용자 요청 (분석 대상)
{USER_PROMPT}
"""


PLAN_MARKDOWN_RULES = """## BACKGROUND
보고서가 생성되는 맥락, 문제 정의, 이슈 상황, 필요성을 명확히 작성하세요.
- 현재 상황 분석
- 문제점 정의
- 이슈의 중요성
- 보고서 필요 이유

## MAIN_CONTENT
전문가 역할이 적용될 분석 프레임워크 기반의 상세 계획 (1-3개 서브항목)을 작성하세요.
- 분석 프레임워크 적용
- 주요 분석 항목
- 구체적 내용 구성
- 상세 섹션 구분

## SUMMARY
전체 계획을 2~3문단으로 압축한 실행 요약을 작성하세요.
- 핵심 내용 요약
- 주요 발견사항
- 예상 효과

## CONCLUSION
전략적 제언, 의사결정 관점, 다음 단계 제안을 작성하세요.
- 전략적 제언
- 의사결정 방향
- 다음 단계 액션
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

**⚠️ 중요: JSON 구조화 응답(Structured Outputs) 모드에서는 아래 Markdown 형식이 적용되지 않습니다.**

Markdown 텍스트 모드에서만 적용:
- # {제목} (H1)
- ## {요약 섹션 제목} (H2)
- ## {배경 섹션 제목} (H2)
- ## {주요내용 섹션 제목} (H2)
- ## {결론 섹션 제목} (H2)

**JSON 응답 모드에서는:**
- content 필드에는 순수 텍스트만 포함하세요
- Markdown 형식(#, ##)을 content에 포함하지 마세요
- 예: "# 제목" ❌ → "제목" ✅
- 예: "## 섹션명" ❌ → "섹션명" ✅

**작성 가이드:**
- JSON 모드: 순수 텍스트만 작성 (형식은 시스템이 추가)
- Markdown 모드: 위의 heading 형식 사용
- 위에 명시된 구조를 정확히 따르세요
- 전문적이고 객관적인 톤을 유지하세요""".strip()


FOR_PLAN_SOUCRE_TYPE_BASIC_PROMPT_SYSTEM= """
당신은 최고급 **보고서 작성 플래너(Planner)**입니다.
당신의 임무는 이전 단계(Call#1)에서 생성된 **고도화 프롬프트(JSON + bullet 기반 output_format)**를 바탕으로,
‘최종 보고서 작성기(Call#3)’가 빠르고 안정적으로 문서를 작성할 수 있도록 가볍고 구조화된 아웃라인을 생성합니다.

중요:
- 이 단계는 보고서 본문 작성 단계가 아닙니다.
- 아웃라인은 ‘핵심 구조’만 남기고, 과도한 분석 요소나 깊은 설명은 포함하지 않습니다.
- Call#3이 처리할 부담을 줄이는 것이 핵심 목표입니다.
(= 생성 수 길이 제한 + 단순화 + 핵심만 유지)

---

### 📌 입력에 대한 이해

- 입력되는 output_format은 JSON이 아니라 ‘섹션명 + bullet’ 형태의 서술 구조입니다.
- 하지만 Bullet을 100% 그대로 쓰지 말고,
  **그중 핵심 의미·관점만 요약하여** 아웃라인을 만들어야 합니다.
- “삭제 금지”가 아니라, **중요 관점만 추출하고 나머지는 정리·축약해야 합니다.**
- Call#3에서 부담이 되므로, 섹션별로 1~3개의 핵심만 남겨야 합니다.
- `output_format`에 포함된 **섹션별 범위, 관점, 다뤄야 할 요소**를 **삭제하거나 임의로 축소·확장해서는 안 됩니다.**

---

### 아웃라인 생성 원칙

1. **문단·긴 문장은 절대 금지.**  
   한 줄짜리 “간결한 bullet 문장”만 생성합니다.

2. **섹션별 규칙 (간소화된 제한)**

   - TITLE: 1개 (핵심 제목 후보)
   - DATE: 1개 (기준일 또는 범위 요약)
   - BACKGROUND: 1개 (시장·기술·환경 중 핵심 하나)
   - MAIN_CONTENT: 2~3개 (너무 많은 축 금지, 가장 중요한 축만)
   - SUMMARY: 1개 (핵심 요약 1줄)
   - CONCLUSION: 1~2개 (최종 결론/전략 포인트)

   **이 범위를 반드시 지키며, 절대로 확장하지 않습니다.**

3. **불필요한 깊이 금지**

   아래 항목들은 계획 단계에서 상세히 다루지 않습니다:
   - 정량 분석(수치·통계)
   - 지역별 세부 구도
   - 기술 아키텍처 상세 구조
   - 규제·정책의 세부 조항
   - 산업별 미시 항목 전체 나열

   → 단 하나의 핵심 주제 또는 관점만 남기고 요약합니다.

4. **섹션 순서 강제**
   TITLE → DATE → BACKGROUND → MAIN_CONTENT → SUMMARY → CONCLUSION  
   JSON도 이 순서 유지.

5. **언어는 자연스러운 한국어.**

---

### 출력 JSON 형식(예시 구조)

아래는 **형태 예시**이며, 실제 내용은 입력된 `output_format`에 맞춰 생성합니다.

```text
{
  "TITLE": ["항목1", "항목2"],
  "DATE": ["항목1"],
  "BACKGROUND": ["항목1", "항목2", "항목3"],
  "MAIN_CONTENT": ["항목1", "항목2", "항목3", "항목4"],
  "SUMMARY": ["항목1", "항목2"],
  "CONCLUSION": ["항목1", "항목2", "항목3"]
}
```

각 `"항목"` 문자열은 **한 줄짜리 bullet 문장**이어야 합니다.
설명식 긴 문단이나 여러 문장을 넣지 마세요.

---

### [출력 형식 규칙 – 매우 중요]

다음 규칙은 **절대적으로 준수해야 합니다.**

1. **반드시 하나의 JSON 객체만 출력**합니다.

   * 키 집합은 정확히 아래 6개여야 합니다.
     `"TITLE"`, `"DATE"`, `"BACKGROUND"`, `"MAIN_CONTENT"`, `"SUMMARY"`, `"CONCLUSION"`
   * 이 6개 키 중 하나라도 빠지거나, 추가 키를 만들면 안 됩니다.

2. **JSON 이외의 어떤 내용도 출력 금지**

   * 설명, 해설, 요약, 마크다운 제목, 리스트, 주석 텍스트 등 **모든 부가 텍스트를 출력하지 마세요.**
   * “아웃라인 설명” 같은 문장도 절대 포함하지 않습니다.

3. **코드 블록 사용 금지**

   * ```json 과 같은 코드 블록 마커를 사용하지 마세요.
     ```
   * 응답 전체는 **순수 JSON 문자열**만 포함해야 합니다.

4. **유효한 JSON 보장**

   * 모든 문자열은 따옴표로 감싸야 합니다.
   * 마지막 요소 뒤에 **쉼표(,)를 남기지 마세요.**
   * 파서가 그대로 `JSON.parse` 혹은 `json.loads` 할 수 있는 형태여야 합니다.

---

위 규칙을 **반드시** 따르세요.
오직 JSON 아웃라인만 생성하고, 그 외의 어떤 텍스트도 출력하지 마세요.

"""

FOR_PLAN_SOUCRE_TYPE_BASIC_PROMPT_USER = """아래는 이전 단계(Call#1)에서 생성된 고도화 프롬프트 결과(JSON + output_format)입니다.
이 내용을 기반으로, 최종 보고서 생성을 위한 '섹션별 아웃라인(계획)'을 생성해주세요.

특히 output_format 영역은 JSON이 아닌 bullet 기반 구조이지만,
각 bullet의 의미를 정확하게 해석하여 섹션별 아웃라인 구성에 반드시 반영해야 합니다.

고도화된 요구사항(JSON):
{{OPTIMIZED_PROMPT_JSON}}

규칙:
- 섹션 구조는 반드시 TITLE → DATE → BACKGROUND → MAIN_CONTENT → SUMMARY → CONCLUSION 순서로 유지.
- output_format의 bullet 내용을 기반으로 섹션별 항목을 1차 구조화해야 함.
- 이 단계에서 문단 또는 장문의 설명을 작성해서는 안 됨.
- 반드시 bullet(항목) 리스트만 작성.
- CALL#3에서 자연스럽게 보고서로 확장될 수 있도록 ‘명확한 소제목·항목 중심’으로 작성.
- TITLE, DATE는 지나치게 확장하지 말고 핵심 정보만 유지.

위 규칙을 기반으로 최종 아웃라인(JSON)을 생성하세요.

"""


def get_prompt_user_default() -> str:
    """보고서 생성 기본 역활을 반환."""
    return PROMPT_USER_DEFAULT

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


def get_for_plan_source_type_basic_prompt_system() -> str:
    """기본 소스 타입용 계획 System Prompt를 반환합니다.

    Returns:
        str: Sequential Planning 2단계(Call#2)에서 아웃라인을 JSON bullet 리스트로
            작성하도록 강제하는 시스템 프롬프트.

    Examples:
        >>> prompt = get_for_plan_source_type_basic_prompt_system()
        >>> "Planner" in prompt and "\"TITLE\"" in prompt
        True
    """
    return FOR_PLAN_SOUCRE_TYPE_BASIC_PROMPT_SYSTEM

def get_for_plan_source_type_basic_prompt_user() -> str:
    """기본 소스 타입용 계획 User Prompt를 반환합니다.

    Returns:
        str: Call#1에서 생성된 고도화 프롬프트(JSON + bullet output_format)를 전달하여
            섹션별 아웃라인 생성을 지시하는 사용자 프롬프트.

    Examples:
        >>> prompt = get_for_plan_source_type_basic_prompt_user()
        >>> "{{OPTIMIZED_PROMPT_JSON}}" in prompt
        True
    """
    return FOR_PLAN_SOUCRE_TYPE_BASIC_PROMPT_USER

def get_plan_markdown_rules() -> str:
    """계획 마크다운 규칙(PLAN_MARKDOWN_RULES)을 반환합니다.

    이 함수는 sequential_planning() 함수에서 2단계 API 호출 시
    prompt_system으로 사용되는 마크다운 규칙을 제공합니다.

    규칙은 4개의 주요 섹션으로 구성됩니다:
    - BACKGROUND: 보고서 배경, 문제 정의, 필요성
    - MAIN_CONTENT: 전문가 역할의 분석 프레임워크 기반 계획
    - SUMMARY: 전체 계획의 2~3문단 요약
    - CONCLUSION: 전략적 제언, 의사결정 방향, 다음 단계

    Returns:
        str: PLAN_MARKDOWN_RULES 상수

    Examples:
        >>> rules = get_plan_markdown_rules()
        >>> "BACKGROUND" in rules
        True
        >>> "MAIN_CONTENT" in rules
        True
        >>> "SUMMARY" in rules
        True
        >>> "CONCLUSION" in rules
        True
    """
    return PLAN_MARKDOWN_RULES


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
    def _normalize(name: str) -> Optional[str]:
        if not name:
            return None
        normalized = name.strip().replace("{{", "").replace("}}", "").strip()
        return normalized or None

    # placeholder가 공백이거나 누락돼도 번호가 밀리지 않도록 순서를 그대로 유지하되,
    # 실제 키가 비어 있으면 스킵한다.
    cleaned: list[str] = []
    for placeholder in placeholders:
        normalized = _normalize(str(placeholder))
        if normalized:
            cleaned.append(normalized)

    if not cleaned:
        return ""

    sections: list[str] = []

    # 1. 제목(H1)
    sections.append(f"#{{{{{cleaned[0]}}}}}")
    sections.append("")

    # 2. 날짜(본문만)
    if len(cleaned) >= 2:
        sections.append(f"{{{{{cleaned[1]}}}}}")
        sections.append("")

    # TODO: H2 번호는 1번부터 시작으로 수정.
    # 3. 나머지 섹션 (H2 번호는 2부터 시작)
    h2_number = 2
    remaining = cleaned[2:] if len(cleaned) > 2 else []
    for idx in range(0, len(remaining), 2):
        title_key = remaining[idx]
        body_key = remaining[idx + 1] if idx + 1 < len(remaining) else None
        sections.append(f"##{h2_number}. {{{{{title_key}}}}}")
        if body_key:
            sections.append(f"{{{{{body_key}}}}}")
        else:
            sections.append("")  # 본문이 비어도 줄바꿈 유지
        sections.append("")
        h2_number += 1

    # 말미 공백 제거
    while sections and sections[-1] == "":
        sections.pop()

    # 연속 빈 줄을 한 줄로 축약해 깨진 줄바꿈을 방지
    collapsed: list[str] = []
    for line in sections:
        if line == "" and collapsed and collapsed[-1] == "":
            continue
        collapsed.append(line)

    markdown_rules = [
        "**출력 템플릿 구조(엄격히 준수)** ",
        "보고서는 아래 구조와 순서로 작성한다:",
        "```",
        *collapsed,
        "```",
        "※ 각 {{placeholder}}는 출력 시 **의미에 맞는 실제 보고서 내용으로 대체**됨.",
        " ※ H2 제목은 항상 **13자 이하로 변환된 제목 문구**로 표현해야 한다.",
    ]
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
    markdown_rule = get_base_report_prompt()

    rules = f"""# 보고서 작성 규칙 
{markdown_rule}

---

커스텀 템플릿 구조 (다음 placeholder들을 포함하여 작성):

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


def create_section_schema(
    source_type: str,
    placeholders: Optional[ListType[DictType[str, Any]]] = None,
) -> dict:
    """소스 타입별 섹션 스키마 JSON 생성.

    Args:
        source_type: "BASIC" 또는 "TEMPLATE"
        placeholders: Template 기반일 때만 사용 (sort 순서로 정렬된 리스트)

    Returns:
        섹션 메타정보 JSON 스키마 (LLM에 전달용)

    Example (BASIC):
        {
          "format": "json",
          "sections": [
            {"id": "TITLE", "type": "TITLE", "required": true, ...},
            {"id": "BACKGROUND", "type": "BACKGROUND", "required": true, ...},
            ...
          ]
        }

    Example (TEMPLATE):
        {
          "format": "json",
          "sections": [
            {"id": "TITLE", "type": "TITLE", "placeholder_key": "{{TITLE}}", ...},
            {"id": "MARKET_ANALYSIS", "type": "SECTION", "placeholder_key": "{{MARKET_ANALYSIS}}", ...}
          ]
        }
    """

    def _resolve_source(raw_source: Any) -> str:
        if hasattr(raw_source, "value"):
            raw_source = raw_source.value
        return str(raw_source or "").strip().upper()

    def _get_attr(item: Any, key: str, default: Any = None) -> Any:
        if isinstance(item, dict):
            return item.get(key, default)
        return getattr(item, key, default)

    def _strip_placeholder_key(value: Optional[str]) -> str:
        if not value:
            return ""
        return value.replace("{{", "").replace("}}", "").strip()

    def _build_basic_sections() -> list[DictType[str, Any]]:
        logger.info("[SCHEMA] Creating BASIC section schema (v1.2)")
        return [
            {
                "id": "TITLE",
                "type": "TITLE",
                "required": True,
                "description": "보고서 제목",
                "max_length": 15,
                "order": 1,
                "source_type": "basic",
            },
            {
                "id": "DATE",
                "type": "DATE",
                "required": True,
                "description": "보고서 작성일 (yyyy.mm.dd)",
                "order": 2,
                "source_type": "system",
            },
            {
                "id": "BACKGROUND",
                "type": "BACKGROUND",
                "required": True,
                "description": "배경 및 목적",
                "max_length": 200,
                "order": 3,
                "source_type": "basic",
            },
            {
                "id": "MAIN_CONTENT",
                "type": "MAIN_CONTENT",
                "required": True,
                "description": "주요 내용",
                "max_length": 1000,
                "order": 4,
                "source_type": "basic",
            },
            {
                "id": "SUMMARY",
                "type": "SUMMARY",
                "required": True,
                "description": "요약",
                "max_length": 500,
                "order": 5,
                "source_type": "basic",
            },
            {
                "id": "CONCLUSION",
                "type": "CONCLUSION",
                "required": True,
                "description": "결론 및 제언",
                "max_length": 500,
                "order": 6,
                "source_type": "basic",
            },
        ]

    def _sort_value(item: Any) -> int:
        sort_value = _get_attr(item, "sort")
        try:
            return int(sort_value)
        except (TypeError, ValueError):
            return 10**6

    def _next_order_factory() -> Any:
        current_order = 1

        def _next_order() -> int:
            nonlocal current_order
            if current_order == 2:
                current_order += 1
            order_value = current_order
            current_order += 1
            return order_value

        return _next_order

    normalized_source = _resolve_source(source_type)

    if normalized_source == "BASIC":
        return {
            "format": "json",
            "sections": _build_basic_sections(),
        }

    if normalized_source != "TEMPLATE":
        raise ValueError(
            f"Unknown source_type: {source_type}. Must be 'BASIC' or 'TEMPLATE'"
        )

    if not placeholders:
        raise ValueError("placeholders required for TEMPLATE source_type")

    logger.info(
        f"[SCHEMA] Creating TEMPLATE section schema (v1.2) - placeholders={len(placeholders)}"
    )

    date_defined = False
    sections: list[DictType[str, Any]] = []
    next_order = _next_order_factory()

    for placeholder in sorted(placeholders, key=_sort_value):
        placeholder_key = _get_attr(placeholder, "placeholder_key")
        placeholder_clean = _strip_placeholder_key(
            str(placeholder_key) if placeholder_key else ""
        )
        if not placeholder_clean:
            placeholder_clean = f"PLACEHOLDER_{len(sections) + 1}"
        normalized_key = placeholder_clean.upper()

        if normalized_key == "DATE":
            sections.append(
                {
                    "id": "DATE",
                    "type": "DATE",
                    "placeholder_key": placeholder_key,
                    "required": True,
                    "description": _get_attr(
                        placeholder, "description", "보고서 작성일 (yyyy.mm.dd)"
                    ),
                    "order": 2,
                    "source_type": "template",
                }
            )
            date_defined = True
            continue

        if "TITLE" in normalized_key:
            sections.append(
                {
                    "id": "TITLE",
                    "type": "TITLE",
                    "placeholder_key": placeholder_key,
                    "required": True,
                    "description": _get_attr(placeholder, "description", "보고서 제목"),
                    "max_length": _get_attr(placeholder, "max_length", 100),
                    "order": next_order(),
                    "source_type": "template",
                }
            )
            continue

        title = _get_attr(placeholder, "title", normalized_key)
        sections.append(
            {
                "id": normalized_key,
                "type": normalized_key or "SECTION",
                "placeholder_key": placeholder_key,
                "required": True,
                "description": _get_attr(
                    placeholder, "description", f"{title} 섹션"
                ),
                "max_length": _get_attr(placeholder, "max_length", 1500),
                "min_length": _get_attr(placeholder, "min_length", 500),
                "example": _get_attr(
                    placeholder, "example", f"{title}에 대한 예시 내용"
                ),
                "order": next_order(),
                "source_type": "template",
            }
        )

    if not date_defined:
        sections.append(
            {
                "id": "DATE",
                "type": "DATE",
                "required": True,
                "description": "보고서 작성일 (yyyy.mm.dd)",
                "order": 2,
                "source_type": "system",
            }
        )

    sections.sort(key=lambda item: item.get("order", 0))

    return {
        "format": "json",
        "sections": sections,
    }


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
