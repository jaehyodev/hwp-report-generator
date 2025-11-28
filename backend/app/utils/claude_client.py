"""
Claude API 클라이언트
보고서 내용을 생성하기 위한 Claude API 통신 모듈
"""
import os
import json
import logging
import re
from typing import Dict, Optional, Union
from datetime import datetime
from anthropic import Anthropic

# shared.constants를 import하면 자동으로 sys.path 설정됨
from shared.constants import ClaudeConfig
from app.utils.prompts import get_default_report_prompt, FINANCIAL_REPORT_SYSTEM_PROMPT

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
MAX_PLAN_CHARS = 20000  # Claude 프롬프트 보호용 Plan 텍스트 최대 길이


class ClaudeClient:
    """Claude API를 사용하여 보고서 내용을 생성하는 클라이언트

    세 가지 메서드 지원:
    - chat_completion(): 기본 모델 (Sonnet 4.5)
    - chat_completion_fast(): 빠른 모델 (Haiku 4.5)
    - chat_completion_reasoning(): 추론 모델 (Opus)
    """

    def __init__(self):
        """Claude 클라이언트 초기화 - 세 가지 모델 로드"""
        self.api_key = os.getenv("CLAUDE_API_KEY")

        if not self.api_key:
            raise ValueError("CLAUDE_API_KEY 환경 변수가 설정되지 않았습니다.")

        # 기본 모델 (Sonnet 4.5)
        self.model = os.getenv("CLAUDE_MODEL", ClaudeConfig.MODEL)

        # 빠른 모델 (Haiku 4.5)
        self.fast_model = os.getenv("CLAUDE_FAST_MODEL", ClaudeConfig.FAST_MODEL)

        # 추론 모델 (Opus)
        self.reasoning_model = os.getenv(
            "CLAUDE_REASONING_MODEL",
            ClaudeConfig.REASONING_MODEL
        )

        self.max_tokens = ClaudeConfig.MAX_TOKENS
        self.client = Anthropic(api_key=self.api_key)

        # 토큰 사용량 추적
        self.last_input_tokens = 0
        self.last_output_tokens = 0
        self.last_total_tokens = 0

    def generate_report(
        self,
        topic: str,
        plan_text: Optional[str] = None,
        system_prompt: Optional[str] = None,
        section_schema: Optional[dict] = None,
        isWebSearch: bool = False
    ) -> Union[str, "StructuredReportResponse"]:
        """주제를 받아 금융 업무보고서 내용을 생성합니다.

        Args:
            topic: 보고서 주제
            plan_text: Sequential Planning에서 전달된 계획 (선택)
            system_prompt: 사용자 지정 시스템 프롬프트 (선택)
            section_schema: 섹션 메타정보 스키마 (JSON 응답 요청시) - Optional[dict]
            isWebSearch: 웹 검색 도구 활성화 여부

        Returns:
            Union[str, StructuredReportResponse]:
                - section_schema가 None: str (Markdown 형식)
                - section_schema가 있음: StructuredReportResponse (JSON) 또는 str (Fallback)

        Examples:
            >>> client = ClaudeClient()
            >>> # Markdown 모드 (기본)
            >>> md_content = client.generate_report("디지털뱅킹 트렌드")
            >>> md_content.startswith("# ")
            True
            >>> # JSON 모드
            >>> schema = {"sections": [...]}
            >>> response = client.generate_report("디지털뱅킹 트렌드", section_schema=schema)
            >>> hasattr(response, 'sections')
            True
        """

        markdown_rule = f"""이 보고서는 **아래 모든 규칙을 절대적으로 준수하여 작성**해야 합니다.

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
9. `###`(H3)이 필요한 경우 ordered list(1., 2. ...)로 대처한다. (H3, H4, ... 사용되지 않는지 점검한다.)
10. 이모티콘을 사용하지 않는다.
11. 웹 검색 결과를 사용하더라도 인용 태그(`<cite>`, `<sup>`, `[1]` 등)를 생성하지 말고, 순수 텍스트만 사용해 내용을 작성합니다.
        """

        # JSON 모드 여부 결정
        use_json_mode = section_schema is not None

        # JSON 모드인 경우 별도 프롬프트 사용
        if use_json_mode:
            return self._generate_report_json(
                topic=topic,
                plan_text=plan_text,
                system_prompt=system_prompt,
                section_schema=section_schema,
                isWebSearch=isWebSearch
            )

        # Markdown 모드: 기존 로직
        base_system_prompt = system_prompt or get_default_report_prompt()
        system_prompt = base_system_prompt  + "\n\n" + markdown_rule

        user_prompt_parts: list[str] = [f"보고서 주제: {topic}".strip()]
        if plan_text:
            safe_plan = plan_text.strip()
            if len(safe_plan) > MAX_PLAN_CHARS:
                logger.warning(
                    f"Plan text truncated from {len(safe_plan)} to {MAX_PLAN_CHARS} chars"
                )
                safe_plan = safe_plan[:MAX_PLAN_CHARS]
            user_prompt_parts.append("보고서 계획:\n" + safe_plan)

        user_prompt = "\n\n".join(part for part in user_prompt_parts if part).strip()

        try:
            logger.info(f"Claude API 호출 시작 - 주제: {topic}")
            logger.info(f"사용 모델: {self.fast_model}")
            logger.info(f"최대 토큰: {self.max_tokens}")
            logger.info(f"웹 검색 사용: {isWebSearch}")

            api_params = {
                "model": self.fast_model,
                "max_tokens": self.max_tokens,
                "system": system_prompt,
                "messages": [
                    {"role": "user", "content": user_prompt}
                ]
            }

            if isWebSearch:
                api_params["tools"] = [
                    {
                        "type": "web_search_20250305",
                        "name": "web_search"
                    }
                ]
                logger.info("웹 검색 도구 활성화됨 (generate_report)")

            message = self.client.messages.create(**api_params)

            # 응답 텍스트 (Markdown)
            logger.info(f"Claude API 응답 객체 정보 (생성 모드):")
            logger.info(f"  - stop_reason: {getattr(message, 'stop_reason', 'N/A')}")
            logger.info(f"  - content 개수: {len(message.content) if message.content else 0}")

            if not message.content:
                # content가 비어있을 때 상세 정보 로깅
                logger.error(f"Claude API content가 비어있습니다! (생성 모드)")
                logger.error(f"  - stop_reason: {getattr(message, 'stop_reason', 'N/A')}")
                logger.error(f"  - usage.input_tokens: {getattr(message.usage, 'input_tokens', 'N/A')}")
                logger.error(f"  - usage.output_tokens: {getattr(message.usage, 'output_tokens', 'N/A')}")
                logger.error(f"  - model: {getattr(message, 'model', 'N/A')}")

                raise ValueError(
                    f"Claude API 응답이 비어있습니다 (생성 모드). "
                    f"stop_reason={getattr(message, 'stop_reason', 'N/A')}, "
                    f"output_tokens={getattr(message.usage, 'output_tokens', 'N/A')}"
                )

            # text 타입 content_block 이 여러 개일 수 있으므로 모두 수집 후 합치기
            text_blocks: list[str] = []
            for content_block in message.content:
                block_text = getattr(content_block, "text", None)

                if isinstance(block_text, str) and block_text:
                    text_blocks.append(block_text)
                    continue

                if isinstance(block_text, dict):
                    candidate = block_text.get("text")
                    if isinstance(candidate, str) and candidate:
                        text_blocks.append(candidate)
                        continue

                if callable(block_text):
                    try:
                        candidate = block_text()
                        if isinstance(candidate, str) and candidate:
                            text_blocks.append(candidate)
                            continue
                    except Exception:
                        pass

                if isinstance(content_block, dict):
                    candidate = content_block.get("text")
                    if isinstance(candidate, str) and candidate:
                        text_blocks.append(candidate)
                        continue

            if not text_blocks:
                raise ValueError(
                    "Claude API 응답에서 텍스트 컨텐츠를 찾을 수 없습니다. "
                    f"Content types: {[getattr(c, 'type', type(c).__name__) for c in message.content]}"
                )

            content = "\n\n".join(text_blocks)

            logger.info("=" * 80)
            logger.info("Claude API 응답 내용 (Markdown):")
            logger.info("=" * 80)
            logger.info(content)
            logger.info("=" * 80)

            logger.info(f"응답 길이: {len(content)} 문자")
            logger.info(f"토큰 사용량 - Input: {message.usage.input_tokens}, Output: {message.usage.output_tokens}")

            # 토큰 사용량 저장
            self.last_input_tokens = getattr(message.usage, "input_tokens", 0)
            self.last_output_tokens = getattr(message.usage, "output_tokens", 0)
            self.last_total_tokens = self.last_input_tokens + self.last_output_tokens

            # Markdown 텍스트 그대로 반환 (파싱은 호출자가 수행)
            return content

        except Exception as e:
            logger.error(f"Claude API 호출 중 오류 발생: {str(e)}")
            raise Exception(f"Claude API 호출 중 오류 발생: {str(e)}")

    def _generate_report_json(
        self,
        topic: str,
        plan_text: Optional[str] = None,
        system_prompt: Optional[str] = None,
        section_schema: Optional[dict] = None,
        isWebSearch: bool = False
    ) -> Union[str, "StructuredReportResponse"]:
        """JSON 모드에서 섹션 구조화 응답을 생성합니다.

        Args:
            topic: 보고서 주제
            plan_text: 계획 텍스트
            system_prompt: 시스템 프롬프트
            section_schema: 섹션 스키마 (필수)
            isWebSearch: 웹 검색 활성화 여부

        Returns:
            Union[str, StructuredReportResponse]: JSON 또는 마크다운 Fallback
        """
        logger.info(f"[JSON_MODE] generate_report 시작 - topic={topic}")

        base_system_prompt = system_prompt or get_default_report_prompt()

        # JSON 응답 요청 프롬프트
        json_instructions = f"""당신은 구조화된 JSON 형식으로 보고서 섹션을 생성하는 전문가입니다.

## 중요 지침

1. **절대로 JSON만 출력하세요** - 설명이나 주석 금지
2. **max_length는 가이드** - 초과할 경우 압축해서 작성하세요.
3. **order 필드 정확성** - 섹션 순서를 order에 명시하세요
4. **DATE 섹션** - source_type=system인 경우 시스템이 생성하지만, 필요시 {{DATE}} 형식으로 요청 가능
5. 웹 검색 결과를 사용하더라도 인용 태그(`<cite>`, `<sup>`, `[1]` 등)를 생성하지 말고, 순수 텍스트만 사용해 내용을 작성합니다.


## 출력 형식 (필수)

다음 JSON 스키마를 **정확히** 따르세요:

```json
{{
  "sections": [
    {{
      "id": "섹션ID",
      "type": "섹션타입",
      "content": "섹션 내용 (자르지 말 것)",
      "order": 1,
      "placeholder_key": "{{PLACEHOLDER_KEY}}" (해당하는 경우)
    }},
    ...
  ]
}}
'''

### [출력 형식 규칙 – 매우 중요]

다음 규칙은 **절대적으로 준수해야 합니다.**

1. **JSON 이외의 어떤 내용도 출력 금지**

   * 설명, 해설, 요약, 마크다운 제목, 리스트, 주석 텍스트 등 **모든 부가 텍스트를 출력하지 마세요.**
   * “아웃라인 설명” 같은 문장도 절대 포함하지 않습니다.

2. **코드 블록 사용 금지**

   * ```json 과 같은 코드 블록 마커를 사용하지 마세요.
     ```
   * 응답 전체는 **순수 JSON 문자열**만 포함해야 합니다.

3. **유효한 JSON 보장**

   * 모든 문자열은 따옴표로 감싸야 합니다.
   * 마지막 요소 뒤에 **쉼표(,)를 남기지 마세요.**
   * 파서가 그대로 `JSON.parse` 혹은 `json.loads` 할 수 있는 형태여야 합니다.

## 필수 섹션 메타정보
{json.dumps(section_schema, ensure_ascii=False, indent=2)}

---
위 지침을 **반드시** 따르세요.
오직 JSON 아웃라인만 생성하고, 그 외의 어떤 텍스트도 출력하지 마세요.

"""

        system_prompt = base_system_prompt + "\n\n" + json_instructions

        user_prompt_parts: list[str] = [f"보고서 주제: {topic}".strip()]
        if plan_text:
            safe_plan = plan_text.strip()
            if len(safe_plan) > MAX_PLAN_CHARS:
                logger.warning(
                    f"[JSON_MODE] Plan text truncated from {len(safe_plan)} to {MAX_PLAN_CHARS} chars"
                )
                safe_plan = safe_plan[:MAX_PLAN_CHARS]
            user_prompt_parts.append("보고서 계획:\n" + safe_plan)

        user_prompt = "\n\n".join(part for part in user_prompt_parts if part).strip()

        try:
            logger.info(f"[JSON_MODE] Claude API 호출 - model={self.fast_model}")

            api_params = {
                "model": self.fast_model,
                "max_tokens": self.max_tokens,
                "system": system_prompt,
                "messages": [
                    {"role": "user", "content": user_prompt}
                ]
            }

            if isWebSearch:
                api_params["tools"] = [
                    {
                        "type": "web_search_20250305",
                        "name": "web_search"
                    }
                ]
                logger.info("[JSON_MODE] 웹 검색 도구 활성화됨")

            message = self.client.messages.create(**api_params)

            # 응답 텍스트 추출
            if not message.content:
                logger.error(f"[JSON_MODE] Claude API content가 비어있습니다!")
                raise ValueError("Claude API 응답이 비어있습니다")

            # text_blocks 수집
            text_blocks: list[str] = []
            for content_block in message.content:
                block_text = getattr(content_block, "text", None)
                if isinstance(block_text, str) and block_text:
                    text_blocks.append(block_text)

            if not text_blocks:
                raise ValueError("Claude API 응답에서 텍스트 컨텐츠를 찾을 수 없습니다")

            content = "\n\n".join(text_blocks)
            logger.info(f"[JSON_MODE] 응답 수신 - length={len(content)}")

            # JSON 파싱 시도
            try:
                jsonUsedContent = re.search(r"```json\s*(\{.*?\})\s*```", content, re.DOTALL)

                if jsonUsedContent : 
                    response_json = json.loads(jsonUsedContent)    
                else :
                    response_json = json.loads(content)    

                #TODO : json.loads 실행 안됨. 필요없는 컨탠츠가 많아서 문제가 되는것 같음. 수정 필요.
                logger.info(f"[JSON_MODE] JSON 파싱 성공")
                return self._process_json_response(response_json, topic)

            except json.JSONDecodeError as e:
                logger.warning(
                    f"[JSON_MODE] JSON 파싱 실패, 마크다운 Fallback 적용 - error={str(e)}"
                )
                # Fallback: 마크다운으로 반환
                return content

        except Exception as e:
            logger.error(f"[JSON_MODE] Claude API 호출 중 오류 발생: {str(e)}")
            raise Exception(f"[JSON_MODE] Claude API 호출 중 오류 발생: {str(e)}")

    def _process_json_response(
        self,
        response_json: dict,
        topic: str
    ) -> "StructuredReportResponse":
        """JSON 응답을 처리하고 StructuredReportResponse로 변환합니다.

        Args:
            response_json: Claude API에서 받은 JSON 응답
            topic: 보고서 주제

        Returns:
            StructuredReportResponse 객체
        """
        from app.models.report_section import (
            StructuredReportResponse,
            SectionMetadata,
            SectionType,
            SourceType,
        )

        logger.info("[JSON_PROCESS] 응답 처리 시작")

        sections_data = response_json.get("sections", [])
        if not isinstance(sections_data, list):
            raise ValueError("'sections' must be a list")

        processed_sections = []

        # DATE 섹션 처리 (규칙 3: LLM DATE 제거, 시스템 DATE로 대체)
        llm_date_section = None
        for section_data in sections_data:
            section_id = section_data.get("id", "")
            section_type = section_data.get("type", "")

            if section_type.upper() == "DATE" or section_id.upper() == "DATE":
                llm_date_section = section_data
                logger.info("[DATE_HANDLING] LLM DATE 섹션 감지 - 시스템 DATE로 대체")
                break

        # 시스템 생성 DATE 섹션 (ORDER=2)
        system_date = datetime.now().strftime("%Y.%m.%d")
        date_section = {
            "id": "DATE",
            "type": "DATE",
            "content": system_date,
            "order": 2,
            "source_type": "system",
        }

        # 섹션 처리
        for section_data in sections_data:
            section_id = section_data.get("id", "")
            section_type_raw = section_data.get("type", "")

            # 로깅 추가 (디버깅용)
            logger.debug(f"[JSON_PROCESS] 섹션 파싱 중 - id={section_id}, type_raw={section_type_raw}")

            # LLM의 DATE 섹션은 스킵 (시스템 DATE로 대체)
            if str(section_type_raw).upper() == "DATE" or str(section_id).upper() == "DATE":
                logger.info(f"[JSON_PROCESS] DATE 섹션 스킵 (시스템 DATE로 대체)")
                continue

            try:
                # ✅ type과 source_type을 명시적으로 Enum으로 변환 (오류 메시지 개선)
                try:
                    section_type = SectionType(section_type_raw) if section_type_raw else SectionType.SECTION
                except ValueError:
                    logger.warning(f"[JSON_PROCESS] 알 수 없는 섹션 타입: {section_type_raw}, SECTION으로 변환")
                    section_type = SectionType.SECTION

                source_type_raw = section_data.get("source_type", "basic")
                try:
                    source_type = SourceType(source_type_raw) if source_type_raw else SourceType.BASIC
                except ValueError:
                    logger.warning(f"[JSON_PROCESS] 알 수 없는 source_type: {source_type_raw}, BASIC으로 변환")
                    source_type = SourceType.BASIC

                section = SectionMetadata(
                    id=section_id,
                    type=section_type,
                    content=section_data.get("content", ""),
                    order=section_data.get("order", len(processed_sections) + 1),
                    placeholder_key=section_data.get("placeholder_key"),
                    source_type=source_type,
                    max_length=section_data.get("max_length"),
                    min_length=section_data.get("min_length"),
                    description=section_data.get("description"),
                    example=section_data.get("example"),
                )
                processed_sections.append(section)
                logger.debug(f"[JSON_PROCESS] 섹션 추가 - id={section_id}, type={section_type}, order={section.order}")

                # max_length 검증 (경고만, 비차단)
                if section.max_length and len(section.content) > section.max_length:
                    logger.warning(
                        f"[SECTION_VALIDATION] Section {section_id} exceeds max_length: "
                        f"{len(section.content)} > {section.max_length}, "
                        f"content will be preserved (not truncated)"
                    )

            except Exception as e:
                logger.error(
                    f"[JSON_PROCESS] Section 처리 오류 - id={section_id}, error={str(e)}",
                    exc_info=True
                )
                continue

        # 시스템 DATE 섹션 추가
        processed_sections.append(
            SectionMetadata(
                id="DATE",
                type="DATE",
                content=system_date,
                order=2,
                source_type="system"
            )
        )

        # 최종 순서로 정렬
        processed_sections.sort(key=lambda s: s.order)

        logger.info(
            f"[JSON_PROCESS] 처리 완료 - sections={len(processed_sections)}"
        )

        return StructuredReportResponse(
            sections=processed_sections,
            metadata={
                "topic": topic,
                "generated_at": system_date,
                "source_type": "json"
            }
        )


    def chat_completion(
        self,
        messages: list[Dict[str, str]],
        system_prompt: str = None,
        isWebSearch: bool = False
    ) -> tuple[str, int, int]:
        """Chat-based completion for conversational report generation.

        Args:
            messages: List of message dictionaries with 'role' and 'content' keys
                     Example: [{"role": "user", "content": "Write a report"}]
            system_prompt: Optional system prompt (default: financial report writer)
            isWebSearch: Whether to enable web search (default: False)

        Returns:
            Tuple of (response_content, input_tokens, output_tokens)

        Raises:
            Exception: If API call fails

        Examples:
            >>> client = ClaudeClient()
            >>> messages = [{"role": "user", "content": "디지털뱅킹 트렌드 보고서 작성"}]
            >>> response, input_tokens, output_tokens = client.chat_completion(messages)
            >>> print(response[:100])
            # 디지털뱅킹 트렌드 분석 보고서

## 요약

2025년 디지털뱅킹 산업은...

            >>> # 웹 검색 활성화
            >>> response, input_tokens, output_tokens = client.chat_completion(
            ...     messages, isWebSearch=True
            ... )
        """
        # Default system prompt for financial reports
        if system_prompt is None:
            system_prompt = FINANCIAL_REPORT_SYSTEM_PROMPT

        try:
            logger.info(f"Claude chat completion 시작 - 메시지 수: {len(messages)}")
            logger.info(f"사용 모델: {self.model}")
            logger.info(f"최대 토큰: {self.max_tokens}")
            logger.info(f"웹 검색 사용: {isWebSearch}")

            # API call 파라미터 구성
            api_params = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "system": system_prompt,
                "messages": messages
            }

            # 웹 검색 활성화 시 tools 추가
            if isWebSearch:
                api_params["tools"] = [
                    {
                        "type": "web_search_20250305", "name" :"web_search"
                    }
                ]
                logger.info("웹 검색 도구 활성화됨")

            # API call with optional web search
            response = self.client.messages.create(**api_params)

            # Extract response content with detailed logging
            logger.info(f"Claude API 응답 객체 정보:")
            logger.info(f"  - stop_reason: {getattr(response, 'stop_reason', 'N/A')}")
            logger.info(f"  - content 개수: {len(response.content) if response.content else 0}")
            logger.info(f"  - model: {getattr(response, 'model', 'N/A')}")

            # 응답 객체 전체 구조 확인
            try:
                import json
                response_dict = response.model_dump() if hasattr(response, 'model_dump') else response.dict()
                logger.debug(f"응답 JSON: {json.dumps(response_dict, default=str, indent=2)}")
            except Exception as e:
                logger.error(f"응답 JSON 변환 실패: {str(e)}")
                logger.error(f"응답 객체 타입: {type(response)}")
                logger.error(f"응답 객체 속성: {dir(response)}")

            if response.content:
                for i, content_block in enumerate(response.content):
                    logger.debug(f"  - content[{i}] 타입: {type(content_block).__name__}")
                    if hasattr(content_block, 'text'):
                        logger.debug(f"    - text 길이: {len(content_block.text)}")
                    if hasattr(content_block, 'type'):
                        logger.debug(f"    - type 속성: {content_block.type}")

            if not response.content:
                # content가 비어있을 때 상세 정보 로깅
                logger.error(f"Claude API content가 비어있습니다!")
                logger.error(f"  - stop_reason: {getattr(response, 'stop_reason', 'N/A')}")
                logger.error(f"  - usage.input_tokens: {getattr(response.usage, 'input_tokens', 'N/A')}")
                logger.error(f"  - usage.output_tokens: {getattr(response.usage, 'output_tokens', 'N/A')}")
                logger.error(f"  - model: {getattr(response, 'model', 'N/A')}")
                logger.error(f"  - id: {getattr(response, 'id', 'N/A')}")

                # API 메시지 내용 확인 (디버깅용)
                logger.error(f"  - 요청한 메시지 개수: {len(messages)}")
                logger.error(f"  - 시스템 프롬프트 길이: {len(system_prompt) if system_prompt else 0}")

                raise ValueError(
                    f"Claude API 응답이 비어있습니다. "
                    f"stop_reason={getattr(response, 'stop_reason', 'N/A')}, "
                    f"output_tokens={getattr(response.usage, 'output_tokens', 'N/A')}"
                )

            # text 타입 content_block 이 여러 개일 수 있으므로 모두 수집 후 합치기
            text_blocks: list[str] = []
            for content_block in response.content:
                block_text = getattr(content_block, "text", None)

                if isinstance(block_text, str) and block_text:
                    text_blocks.append(block_text)
                    continue

                if isinstance(block_text, dict):
                    candidate = block_text.get("text")
                    if isinstance(candidate, str) and candidate:
                        text_blocks.append(candidate)
                        continue

                if callable(block_text):
                    try:
                        candidate = block_text()
                        if isinstance(candidate, str) and candidate:
                            text_blocks.append(candidate)
                            continue
                    except Exception:
                        pass

                if isinstance(content_block, dict):
                    candidate = content_block.get("text")
                    if isinstance(candidate, str) and candidate:
                        text_blocks.append(candidate)
                        continue

            if not text_blocks:
                raise ValueError(
                    "Claude API 응답에서 텍스트 컨텐츠를 찾을 수 없습니다. "
                    f"Content types: {[getattr(c, 'type', type(c).__name__) for c in response.content]}"
                )

            content = "\n\n".join(text_blocks)

            logger.info("=" * 80)
            logger.info("Claude API 응답 (채팅 모드):")
            logger.info("=" * 80)
            logger.info(content[:500] + "..." if len(content) > 500 else content)
            logger.info("=" * 80)

            logger.info(f"응답 길이: {len(content)} 문자")
            logger.info(f"토큰 사용량 - Input: {response.usage.input_tokens}, Output: {response.usage.output_tokens}")

            # Track token usage
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens

            self.last_input_tokens = input_tokens
            self.last_output_tokens = output_tokens
            self.last_total_tokens = input_tokens + output_tokens

            return content, input_tokens, output_tokens

        except Exception as e:
            logger.error(f"Claude chat completion 중 오류 발생: {str(e)}")
            raise Exception(f"Claude chat completion 중 오류 발생: {str(e)}")

    def chat_completion_fast(
        self,
        messages: list[Dict[str, str]],
        system_prompt: str = None,
        isWebSearch: bool = False
    ) -> tuple[str, int, int]:
        """빠른 모델(Haiku)을 사용한 Chat completion - 개요, 계획, 요약용

        Args:
            messages: 메시지 리스트
            system_prompt: 시스템 프롬프트
            isWebSearch: 웹 검색 활성화 여부

        Returns:
            (응답 텍스트, input_tokens, output_tokens)
        """
        return self._call_claude(
            model=self.fast_model,
            messages=messages,
            system_prompt=system_prompt,
            isWebSearch=isWebSearch,
            model_name="Haiku (빠른)"
        )

    def chat_completion_reasoning(
        self,
        messages: list[Dict[str, str]],
        system_prompt: str = None,
        isWebSearch: bool = False
    ) -> tuple[str, int, int]:
        """추론 모델(Opus)을 사용한 Chat completion - 복잡 분석용

        Args:
            messages: 메시지 리스트
            system_prompt: 시스템 프롬프트
            isWebSearch: 웹 검색 활성화 여부

        Returns:
            (응답 텍스트, input_tokens, output_tokens)
        """
        return self._call_claude(
            model=self.reasoning_model,
            messages=messages,
            system_prompt=system_prompt,
            isWebSearch=isWebSearch,
            model_name="Opus (추론)"
        )

    def _call_claude(
        self,
        model: str,
        messages: list[Dict[str, str]],
        system_prompt: str = None,
        isWebSearch: bool = False,
        model_name: str = "Unknown"
    ) -> tuple[str, int, int]:
        """공통 Claude API 호출 로직

        Args:
            model: 사용할 모델 ID
            messages: 메시지 리스트
            system_prompt: 시스템 프롬프트
            isWebSearch: 웹 검색 활성화
            model_name: 로깅용 모델명

        Returns:
            (응답 텍스트, input_tokens, output_tokens)
        """
        if system_prompt is None:
            system_prompt = FINANCIAL_REPORT_SYSTEM_PROMPT

        try:
            logger.info(f"Claude API 호출 - 모델: {model_name}, 메시지: {len(messages)}")

            # API call 파라미터
            api_params = {
                "model": model,
                "max_tokens": self.max_tokens,
                "system": system_prompt,
                "messages": messages
            }

            # 웹 검색 활성화 시
            if isWebSearch:
                api_params["tools"] = [
                    {
                        "type": "web_search_20250305",
                        "name": "web_search"
                    }
                ]
                logger.info("웹 검색 도구 활성화")

            # API call
            response = self.client.messages.create(**api_params)

            # 응답 검증
            if not response.content:
                raise ValueError(f"Claude API 응답이 비어있습니다")

            text_blocks: list[str] = []
            for content_block in response.content:
                block_text = getattr(content_block, "text", None)

                if isinstance(block_text, str) and block_text:
                    text_blocks.append(block_text)
                    continue

                if isinstance(block_text, dict):
                    candidate = block_text.get("text")
                    if isinstance(candidate, str) and candidate:
                        text_blocks.append(candidate)
                        continue

                if callable(block_text):
                    try:
                        candidate = block_text()
                        if isinstance(candidate, str) and candidate:
                            text_blocks.append(candidate)
                            continue
                    except Exception:
                        pass

                if isinstance(content_block, dict):
                    candidate = content_block.get("text")
                    if isinstance(candidate, str) and candidate:
                        text_blocks.append(candidate)
                        continue

            if not text_blocks:
                raise ValueError(f"Claude API에서 텍스트를 찾을 수 없습니다")

            # 토큰 저장
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens

            self.last_input_tokens = input_tokens
            self.last_output_tokens = output_tokens
            self.last_total_tokens = input_tokens + output_tokens

            logger.info(f"응답 완료 - {model_name}, Input: {input_tokens}, Output: {output_tokens}")

            text_content = "\n\n".join(text_blocks)

            return text_content, input_tokens, output_tokens

        except Exception as e:
            logger.error(f"Claude API 오류 ({model_name}): {str(e)}")
            raise Exception(f"Claude API 오류 ({model_name}): {str(e)}")

    def get_token_usage(self) -> Dict[str, int]:
        """Gets the last API call's token usage.

        Returns:
            Dictionary with input_tokens, output_tokens, total_tokens

        Examples:
            >>> client = ClaudeClient()
            >>> client.chat_completion([{"role": "user", "content": "Test"}])
            >>> usage = client.get_token_usage()
            >>> print(usage["total_tokens"])
            1250
        """
        return {
            "input_tokens": self.last_input_tokens,
            "output_tokens": self.last_output_tokens,
            "total_tokens": self.last_total_tokens
        }
