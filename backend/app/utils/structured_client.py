"""
Claude API Structured Outputs를 사용한 전용 클라이언트

Structured Outputs는 Claude API에서 JSON 응답을 강제로 보장하는 기능입니다.
이 클라이언트는 다음을 제공합니다:
- BASIC 모드: 고정된 섹션 구조 (TITLE, DATE, BACKGROUND, MAIN_CONTENT, SUMMARY, CONCLUSION)
- TEMPLATE 모드: 동적 섹션 구조 (placeholder 기반)
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from anthropic import Anthropic

from shared.constants import ClaudeConfig
from app.utils.prompts import get_default_report_prompt

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class StructuredClaudeClient:
    """Claude API Structured Outputs를 사용한 전용 클라이언트

    Structured Outputs는 Claude API에서 JSON 응답을 강제로 보장하는 기능입니다.
    이를 통해 항상 유효한 JSON 응답을 얻을 수 있습니다.
    """

    def __init__(self):
        """Anthropic 클라이언트 초기화"""
        self.api_key = os.getenv("CLAUDE_API_KEY")

        if not self.api_key:
            raise ValueError("CLAUDE_API_KEY 환경 변수가 설정되지 않았습니다.")

        # 기본 모델 (Sonnet 4.5)
        self.model = os.getenv("CLAUDE_MODEL", ClaudeConfig.MODEL)
        self.max_tokens = ClaudeConfig.MAX_TOKENS
        self.client = Anthropic(api_key=self.api_key)

        # 토큰 사용량 추적
        self.last_input_tokens = 0
        self.last_output_tokens = 0
        self.last_total_tokens = 0

        logger.info(f"[STRUCTURED_CLIENT] 초기화 완료 - model={self.model}")

    def generate_structured_report(
        self,
        topic: str,
        system_prompt: str,
        section_schema: dict,
        source_type: str,
        context_messages: Optional[List[dict]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000
    ) -> "StructuredReportResponse":
        """구조화된 보고서 생성 (Structured Outputs 사용)

        Args:
            topic: 보고서 주제
            system_prompt: 시스템 프롬프트
            section_schema: 섹션 스키마 (create_section_schema 결과)
            source_type: "basic" 또는 "template" (JSON Schema 동적 생성용)
            context_messages: 선택 메시지 (대화형)
            temperature: Claude 온도 값 (0-1)
            max_tokens: 최대 토큰 수

        Returns:
            StructuredReportResponse 객체 (항상 유효한 JSON)

        Raises:
            ValueError: JSON Schema 검증 실패
            Exception: Claude API 호출 실패
        """
        logger.info(f"[STRUCTURED_REPORT] 시작 - topic={topic}, source_type={source_type}")

        # JSON Schema 빌드
        json_schema = self._build_json_schema(section_schema, source_type)
        logger.info(f"[STRUCTURED_REPORT] JSON Schema 생성 완료")

        # User message 구성
        user_message = self._build_user_message(topic, section_schema)

        # 메시지 구성
        messages = []

        # 컨텍스트 메시지가 있으면 추가 (대화형 모드)
        if context_messages:
            messages.extend(context_messages)

        # 현재 사용자 메시지 추가
        messages.append({
            "role": "user",
            "content": user_message
        })

        logger.debug(f"[STRUCTURED_REPORT] 메시지 수: {len(messages)}")

        # Structured Outputs로 Claude API 호출
        response_json = self._invoke_with_structured_output(
            system_prompt=system_prompt,
            messages=messages,
            json_schema=json_schema,
            temperature=temperature,
            max_tokens=max_tokens
        )

        # StructuredReportResponse로 파싱
        return self._process_response(response_json, topic, source_type)

    def _build_json_schema(self, section_schema: dict, source_type: str) -> dict:
        """StructuredReportResponse의 JSON Schema 생성 (동적)

        Args:
            section_schema: create_section_schema() 결과
            source_type: "basic" 또는 "template"

        Returns:
            JSON Schema dict (type enum은 source_type에 따라 동적 또는 자유형)

        Logic:
            1. BASIC 모드:
               - type enum = ["TITLE", "DATE", "BACKGROUND", "MAIN_CONTENT", "SUMMARY", "CONCLUSION"] (고정)
               - source_type enum = ["basic", "system"]
            2. TEMPLATE 모드:
               - type = 문자열 자유형 (enum 제약 없음, placeholder id와 일치)
               - source_type enum = ["template", "system"]
        """
        logger.debug(f"[JSON_SCHEMA] 빌드 시작 - source_type={source_type}")

        # 정규화된 source_type
        normalized_source = str(source_type).strip().lower()

        # 기본 JSON Schema 구조
        base_schema = {
            "type": "object",
            "properties": {
                "sections": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {
                                "type": "string",
                                "description": "섹션 ID (예: TITLE, MARKET_ANALYSIS)"
                            },
                            "type": {
                                # ⭐ 동적으로 결정됨 (아래에서)
                            },
                            "content": {
                                "type": "string",
                                "description": "섹션 내용"
                            },
                            "order": {
                                "type": "integer",
                                "description": "섹션 순서 (1-based)",
                                "minimum": 1
                            },
                            "source_type": {
                                # ⭐ 동적으로 결정됨 (아래에서)
                            },
                            "placeholder_key": {
                                "type": ["string", "null"],
                                "description": "템플릿 placeholder_key ({{KEY}} 형식)"
                            },
                            "max_length": {
                                "type": ["integer", "null"],
                                "description": "최대 문자 길이"
                            },
                            "min_length": {
                                "type": ["integer", "null"],
                                "description": "최소 문자 길이"
                            },
                            "description": {
                                "type": ["string", "null"],
                                "description": "섹션 설명"
                            },
                            "example": {
                                "type": ["string", "null"],
                                "description": "예시 값"
                            }
                        },
                        "required": ["id", "type", "content", "order", "source_type"]
                    }
                },
                "metadata": {
                    "type": ["object", "null"],
                    "description": "메타데이터 (생성일, 모델 등)"
                }
            },
            "required": ["sections"]
        }

        # BASIC 모드: type enum 고정
        if normalized_source == "basic":
            logger.debug("[JSON_SCHEMA] BASIC 모드 - type enum 고정")
            base_schema["properties"]["sections"]["items"]["properties"]["type"] = {
                "type": "string",
                "enum": ["TITLE", "DATE", "BACKGROUND", "MAIN_CONTENT", "SUMMARY", "CONCLUSION"],
                "description": "섹션 타입 (고정)"
            }
            base_schema["properties"]["sections"]["items"]["properties"]["source_type"] = {
                "type": "string",
                "enum": ["basic", "system"],
                "description": "섹션 출처"
            }

        # TEMPLATE 모드: type 문자열 자유형
        elif normalized_source == "template":
            logger.debug("[JSON_SCHEMA] TEMPLATE 모드 - type 문자열 자유형")
            base_schema["properties"]["sections"]["items"]["properties"]["type"] = {
                "type": "string",
                "description": "섹션 타입 (동적, placeholder id와 일치)"
            }
            base_schema["properties"]["sections"]["items"]["properties"]["source_type"] = {
                "type": "string",
                "enum": ["template", "system"],
                "description": "섹션 출처"
            }

        else:
            raise ValueError(f"Unknown source_type: {source_type}. Must be 'basic' or 'template'")

        logger.debug(f"[JSON_SCHEMA] 빌드 완료")
        return base_schema

    def _invoke_with_structured_output(
        self,
        system_prompt: str,
        messages: List[dict],
        json_schema: dict,
        temperature: float = 0.7,
        max_tokens: int = 4000
    ) -> dict:
        """Structured Outputs로 Claude API 호출

        Args:
            system_prompt: 시스템 프롬프트
            messages: 메시지 리스트
            json_schema: Structured Output JSON Schema
            temperature: 온도 값
            max_tokens: 최대 토큰 수

        Returns:
            검증된 JSON dict (Claude가 보장)
        """
        logger.info("[INVOKE_STRUCTURED] Claude API 호출 시작")

        try:
            logger.debug(f"[INVOKE_STRUCTURED] API 파라미터 구성 중")
            logger.debug(f"  - model: {self.model}")
            logger.debug(f"  - max_tokens: {max_tokens}")
            logger.debug(f"  - messages count: {len(messages)}")

            # Structured Outputs 파라미터 - response_format 지원
            # Note: Anthropic SDK 최신 버전에서 response_format 지원
            api_params = {
                "model": self.model,
                "max_tokens": max_tokens,
                "system": system_prompt,
                "messages": messages,
                "temperature": temperature,
            }

            # response_format을 시도 - SDK 버전에 따라 처리
            try:
                api_params["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "StructuredReportResponse",
                        "schema": json_schema,
                        "strict": True  # 엄격한 모드: schema 정확히 준수
                    }
                }
                logger.debug("[INVOKE_STRUCTURED] response_format 파라미터 추가 완료")
            except Exception as e:
                logger.warning(f"[INVOKE_STRUCTURED] response_format 설정 오류: {str(e)}")
                logger.warning("[INVOKE_STRUCTURED] Fallback: response_format 없이 진행")

            # Claude API 호출
            logger.debug(f"[INVOKE_STRUCTURED] Claude API 호출 (response_format 포함 여부 확인 중)")
            try:
                message = self.client.messages.create(**api_params)
            except TypeError as te:
                # response_format이 지원되지 않는 경우, response_format 제거 후 재시도
                if "response_format" in str(te):
                    logger.warning(f"[INVOKE_STRUCTURED] response_format 미지원 감지 - 파라미터 제거 후 재시도")
                    del api_params["response_format"]
                    message = self.client.messages.create(**api_params)
                else:
                    raise

            # 응답 추출
            if not message.content:
                logger.error("[INVOKE_STRUCTURED] Claude API content가 비어있습니다!")
                raise ValueError("Claude API 응답이 비어있습니다")

            # 텍스트 블록 수집
            text_blocks: List[str] = []
            for content_block in message.content:
                block_text = getattr(content_block, "text", None)
                if isinstance(block_text, str) and block_text:
                    text_blocks.append(block_text)

            if not text_blocks:
                raise ValueError("Claude API 응답에서 텍스트 컨텐츠를 찾을 수 없습니다")

            response_text = "\n\n".join(text_blocks)
            logger.debug(f"[INVOKE_STRUCTURED] 응답 수신 - length={len(response_text)}")

            # JSON 파싱
            try:
                response_json = json.loads(response_text)
                logger.info(f"[INVOKE_STRUCTURED] JSON 파싱 성공")
            except json.JSONDecodeError as e:
                logger.error(f"[INVOKE_STRUCTURED] JSON 파싱 실패: {str(e)}")
                logger.error(f"[INVOKE_STRUCTURED] 응답 내용: {response_text[:500]}...")
                raise ValueError(f"JSON 파싱 실패: {str(e)}")

            # 토큰 사용량 저장
            self.last_input_tokens = getattr(message.usage, "input_tokens", 0)
            self.last_output_tokens = getattr(message.usage, "output_tokens", 0)
            self.last_total_tokens = self.last_input_tokens + self.last_output_tokens

            logger.info(
                f"[INVOKE_STRUCTURED] API 호출 완료 - "
                f"tokens(input={self.last_input_tokens}, output={self.last_output_tokens})"
            )

            return response_json

        except Exception as e:
            logger.error(f"[INVOKE_STRUCTURED] Claude API 호출 중 오류 발생: {str(e)}")
            raise Exception(f"Claude API Structured Outputs 호출 실패: {str(e)}")

    def _build_user_message(self, topic: str, section_schema: dict) -> str:
        """Claude에 전달할 User Message 빌드

        Args:
            topic: 보고서 주제
            section_schema: 섹션 스키마

        Returns:
            User message 문자열
        """
        sections_info = json.dumps(section_schema, ensure_ascii=False, indent=2)

        message = f"""당신은 구조화된 JSON 형식으로 보고서 섹션을 생성하는 전문가입니다.

## 보고서 주제
{topic}

## 필수 섹션 메타정보

아래 섹션 정의를 따라 JSON 형식으로 보고서를 작성하세요:

{sections_info}

## 중요 지침

1. **반드시 JSON만 출력하세요** - 설명이나 주석 금지
2. **max_length/min_length는 가이드** - 초과할 경우 내용을 적절히 조정하세요
3. **order 필드 정확성** - 섹션 순서를 order에 명시하세요
4. **content는 자르지 말 것** - 필요시 min_length 범위 내에서 압축하세요
5. **모든 필수 섹션을 포함하세요** - 누락된 섹션이 없도록 확인
6. **JSON 유효성 보장** - 모든 문자열은 따옴표로 감싸고, 마지막 쉼표 제거

이제 위의 섹션 정의에 맞춰 JSON 형식의 보고서를 생성하세요."""

        return message

    def _process_response(
        self,
        response_json: dict,
        topic: str,
        source_type: str
    ) -> "StructuredReportResponse":
        """JSON 응답을 처리하고 StructuredReportResponse로 변환합니다.

        Args:
            response_json: Claude API에서 받은 JSON 응답
            topic: 보고서 주제
            source_type: "basic" 또는 "template"

        Returns:
            StructuredReportResponse 객체
        """
        from app.models.report_section import (
            StructuredReportResponse,
            SectionMetadata,
            SourceType,
        )

        logger.info("[PROCESS_RESPONSE] 응답 처리 시작")

        sections_data = response_json.get("sections", [])
        if not isinstance(sections_data, list):
            raise ValueError("'sections' must be a list")

        processed_sections = []

        # 시스템 생성 DATE 섹션 (ORDER=2)
        system_date = datetime.now().strftime("%Y.%m.%d")

        # LLM의 DATE 섹션 감지 및 제거
        llm_has_date = any(
            str(s.get("id", "")).upper() == "DATE" or str(s.get("type", "")).upper() == "DATE"
            for s in sections_data
        )

        # 섹션 처리
        for section_data in sections_data:
            section_id = section_data.get("id", "")
            section_type = section_data.get("type", "")

            logger.debug(f"[PROCESS_RESPONSE] 섹션 파싱 - id={section_id}, type={section_type}")

            # LLM의 DATE 섹션은 스킵 (시스템 DATE로 대체)
            if str(section_type).upper() == "DATE" or str(section_id).upper() == "DATE":
                logger.info(f"[PROCESS_RESPONSE] DATE 섹션 스킵 (시스템 DATE로 대체)")
                continue

            try:
                # source_type 처리
                source_type_raw = section_data.get("source_type", "basic")
                try:
                    source_type_enum = SourceType(source_type_raw) if source_type_raw else SourceType.BASIC
                except ValueError:
                    logger.warning(f"[PROCESS_RESPONSE] 알 수 없는 source_type: {source_type_raw}, BASIC으로 변환")
                    source_type_enum = SourceType.BASIC

                section = SectionMetadata(
                    id=section_id,
                    type=section_type,  # ⭐ 이제 str이므로 직접 할당 가능
                    content=section_data.get("content", ""),
                    order=section_data.get("order", 0),
                    source_type=source_type_enum,
                    placeholder_key=section_data.get("placeholder_key"),
                    max_length=section_data.get("max_length"),
                    min_length=section_data.get("min_length"),
                    description=section_data.get("description"),
                    example=section_data.get("example")
                )

                processed_sections.append(section)
                logger.debug(f"[PROCESS_RESPONSE] 섹션 추가 완료 - id={section_id}, order={section.order}")

            except Exception as e:
                logger.error(f"[PROCESS_RESPONSE] 섹션 파싱 오류 - id={section_id}: {str(e)}", exc_info=True)
                raise

        # 시스템 DATE 섹션 추가 (order=2)
        date_section = SectionMetadata(
            id="DATE",
            type="DATE",
            content=system_date,
            order=2,
            source_type=SourceType.SYSTEM
        )
        processed_sections.append(date_section)
        logger.info(f"[PROCESS_RESPONSE] 시스템 DATE 섹션 추가")

        # order로 정렬
        processed_sections.sort(key=lambda s: s.order)

        # StructuredReportResponse 생성
        response = StructuredReportResponse(
            sections=processed_sections,
            metadata={
                "generated_at": datetime.now().isoformat(),
                "model": self.model,
                "topic": topic,
                "source_type": source_type,
                "total_sections": len(processed_sections)
            }
        )

        logger.info(f"[PROCESS_RESPONSE] 응답 처리 완료 - sections={len(processed_sections)}")
        return response
