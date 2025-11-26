"""
Claude API 클라이언트
보고서 내용을 생성하기 위한 Claude API 통신 모듈
"""
import os
import logging
from typing import Dict, Optional
from anthropic import Anthropic

# shared.constants를 import하면 자동으로 sys.path 설정됨
from shared.constants import ClaudeConfig
from app.utils.prompts import get_default_report_prompt

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

        logger.info(f"ClaudeClient 초기화 완료")
        logger.info(f"  - 기본 모델: {self.model}")
        logger.info(f"  - 빠른 모델: {self.fast_model}")
        logger.info(f"  - 추론 모델: {self.reasoning_model}")

    def generate_report(
        self,
        topic: str,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        isWebSearch: bool = False
    ) -> str:
        """주제를 받아 금융 업무보고서 내용을 Markdown 형식으로 생성합니다.

        Args:
            topic: 보고서 주제
            plan_text: Sequential Planning에서 전달된 계획 (선택)
            system_prompt: 사용자 지정 시스템 프롬프트 (선택)
            isWebSearch: 웹 검색 도구 활성화 여부

        Returns:
            str: Markdown 형식의 보고서 텍스트

        Examples:
            >>> client = ClaudeClient()
            >>> md_content = client.generate_report("디지털뱅킹 트렌드")
            >>> md_content.startswith("# ")
            True
        """
        base_system_prompt = system_prompt or get_default_report_prompt()


        try:
            logger.info(f"Claude API 호출 시작 - 주제: {topic}")
            logger.info(f"사용 모델: {self.model}")
            logger.info(f"최대 토큰: {self.max_tokens}")
            logger.info(f"웹 검색 사용: {isWebSearch}")

            api_params = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "system": base_system_prompt,
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
            text_blocks = []
            for content_block in message.content:
                block_type = getattr(content_block, "type", None)
                block_text = getattr(content_block, "text", None)

                if block_text and (block_type == "text" or block_type is None):
                    text_blocks.append(block_text)

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
            self.last_input_tokens = message.usage.input_tokens
            self.last_output_tokens = message.usage.output_tokens
            self.last_total_tokens = self.last_input_tokens + self.last_output_tokens

            # Markdown 텍스트 그대로 반환 (파싱은 호출자가 수행)
            return content

        except Exception as e:
            logger.error(f"Claude API 호출 중 오류 발생: {str(e)}")
            raise Exception(f"Claude API 호출 중 오류 발생: {str(e)}")


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
            text_blocks = []
            for content_block in response.content:
                block_type = getattr(content_block, "type", None)
                block_text = getattr(content_block, "text", None)

                if block_text and (block_type == "text" or block_type is None):
                    text_blocks.append(block_text)

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

            text_content = None
            for content_block in response.content:
                if hasattr(content_block, 'text'):
                    text_content = content_block.text
                    break

            if not text_content:
                raise ValueError(f"Claude API에서 텍스트를 찾을 수 없습니다")

            # 토큰 저장
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens

            self.last_input_tokens = input_tokens
            self.last_output_tokens = output_tokens
            self.last_total_tokens = input_tokens + output_tokens

            logger.info(f"응답 완료 - {model_name}, Input: {input_tokens}, Output: {output_tokens}")

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
