"""
Claude API 클라이언트 테스트
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from app.utils.claude_client import ClaudeClient


@pytest.fixture
def mock_claude_response():
    """Claude API 응답 mock (Markdown 형식)"""
    mock_response = Mock()
    mock_response.content = [
        Mock(text="""# 디지털 뱅킹 혁신 보고서

## 핵심 요약

디지털 뱅킹은 AI와 빅데이터를 활용하여 고객 경험을 혁신하고 있습니다.

## 추진 배경

최근 디지털 금융 환경의 급격한 변화로 인해 은행들은 새로운 기술 도입이 필수적입니다.

## 주요 혁신 동향

1. AI 기반 개인화 서비스
2. 블록체인 기술 활용
3. 모바일 우선 전략

## 향후 과제

지속적인 기술 투자와 인재 육성이 필요합니다.""")
    ]
    mock_response.usage = Mock(
        input_tokens=1500,
        output_tokens=3200
    )
    return mock_response


@pytest.mark.unit
class TestClaudeClientInit:
    """ClaudeClient 초기화 테스트"""

    @patch.dict('os.environ', {'CLAUDE_API_KEY': 'test_api_key', 'CLAUDE_MODEL': 'claude-sonnet-4-5-20250929'})
    def test_init_success(self):
        """정상 초기화 테스트"""
        client = ClaudeClient()

        assert client.api_key == 'test_api_key'
        assert client.model == 'claude-sonnet-4-5-20250929'
        assert client.client is not None
        assert client.last_input_tokens == 0
        assert client.last_output_tokens == 0
        assert client.last_total_tokens == 0

    def test_init_missing_api_key(self, monkeypatch):
        """API 키 누락 시 ValueError 발생"""
        monkeypatch.delenv('CLAUDE_API_KEY', raising=False)

        with pytest.raises(ValueError) as exc_info:
            ClaudeClient()

        assert "CLAUDE_API_KEY" in str(exc_info.value)

    @patch.dict('os.environ', {'CLAUDE_API_KEY': 'test_api_key'})
    def test_init_default_model(self, monkeypatch):
        """기본 모델 설정 확인"""
        monkeypatch.delenv('CLAUDE_MODEL', raising=False)

        client = ClaudeClient()

        # 기본값 확인 (main.py나 claude_client.py에서 설정된 기본값)
        assert client.model is not None


@pytest.mark.unit
class TestClaudeClientGenerateReport:
    """보고서 생성 테스트"""

    @patch.dict('os.environ', {'CLAUDE_API_KEY': 'test_api_key'})
    @patch('app.utils.claude_client.Anthropic')
    def test_generate_report_success(self, mock_anthropic_class, mock_claude_response):
        """보고서 생성 성공 테스트 - Markdown 반환"""
        # Mock 설정
        mock_client_instance = Mock()
        mock_anthropic_class.return_value = mock_client_instance
        mock_client_instance.messages.create.return_value = mock_claude_response

        client = ClaudeClient()
        result = client.generate_report("2025년 디지털 뱅킹 트렌드")

        # Markdown 문자열 반환 검증
        assert isinstance(result, str)
        assert len(result) > 0
        assert "# 디지털 뱅킹" in result
        assert "## " in result  # H2 헤더가 있는지 확인

        # 내용 검증
        assert "AI 기반 개인화 서비스" in result
        assert "핵심 요약" in result

        # API 호출 확인
        mock_client_instance.messages.create.assert_called_once()

    @patch.dict('os.environ', {'CLAUDE_API_KEY': 'test_api_key'})
    @patch('app.utils.claude_client.Anthropic')
    def test_generate_report_with_valid_structure(self, mock_anthropic_class, mock_claude_response):
        """반환된 보고서 Markdown 구조 검증"""
        mock_client_instance = Mock()
        mock_anthropic_class.return_value = mock_client_instance
        mock_client_instance.messages.create.return_value = mock_claude_response

        client = ClaudeClient()
        result = client.generate_report("테스트 주제")

        # Markdown 필수 요소 확인
        assert isinstance(result, str)
        assert "# " in result  # H1 제목
        assert "## " in result  # H2 섹션 헤더
        assert len(result) > 50  # 최소 길이

    @patch.dict('os.environ', {'CLAUDE_API_KEY': 'test_api_key'})
    @patch('app.utils.claude_client.Anthropic')
    def test_generate_report_tracks_token_usage(self, mock_anthropic_class, mock_claude_response):
        """토큰 사용량 추적 테스트"""
        mock_client_instance = Mock()
        mock_anthropic_class.return_value = mock_client_instance
        mock_client_instance.messages.create.return_value = mock_claude_response

        client = ClaudeClient()
        client.generate_report("테스트 주제")

        # 토큰 사용량 확인
        assert client.last_input_tokens == 1500
        assert client.last_output_tokens == 3200
        assert client.last_total_tokens == 4700

    @patch.dict('os.environ', {'CLAUDE_API_KEY': 'test_api_key'})
    @patch('app.utils.claude_client.Anthropic')
    def test_generate_report_api_error(self, mock_anthropic_class):
        """API 호출 실패 시 예외 처리"""
        mock_client_instance = Mock()
        mock_anthropic_class.return_value = mock_client_instance
        mock_client_instance.messages.create.side_effect = Exception("API Error")

        client = ClaudeClient()

        with pytest.raises(Exception) as exc_info:
            client.generate_report("테스트 주제")

        assert "API Error" in str(exc_info.value)

    @patch.dict('os.environ', {'CLAUDE_API_KEY': 'test_api_key'})
    @patch('app.utils.claude_client.Anthropic')
    def test_generate_report_with_plan_text(self, mock_anthropic_class, mock_claude_response):
        """Plan 텍스트가 사용자 메시지에 포함되는지 확인"""
        mock_client_instance = Mock()
        mock_anthropic_class.return_value = mock_client_instance
        mock_client_instance.messages.create.return_value = mock_claude_response

        client = ClaudeClient()
        plan_text = "# 계획\n- 섹션1\n- 섹션2"

        client.generate_report(
            topic="테스트 주제",
            plan_text=plan_text,
            system_prompt="CUSTOM_SYSTEM",
            isWebSearch=False
        )

        call_kwargs = mock_client_instance.messages.create.call_args.kwargs
        sent_message = call_kwargs["messages"][0]["content"]

        assert "보고서 계획" in sent_message
        assert "섹션1" in sent_message
        assert call_kwargs["system"] == "CUSTOM_SYSTEM"


@pytest.mark.unit
class TestClaudeClientChatCompletion:
    """Chat completion 메서드 테스트 (기본, 빠른, 추론)"""

    @pytest.fixture
    def mock_fast_response(self):
        """빠른 모델 응답 mock"""
        mock_response = Mock()
        mock_response.content = [
            Mock(text="요약: 디지털뱅킹은 빠르게 발전하고 있습니다.")
        ]
        mock_response.usage = Mock(
            input_tokens=800,
            output_tokens=150
        )
        return mock_response

    @patch.dict('os.environ', {
        'CLAUDE_API_KEY': 'test_api_key',
        'CLAUDE_MODEL': 'claude-sonnet-4-5-20250929',
        'CLAUDE_FAST_MODEL': 'claude-haiku-4-5-20251001',
        'CLAUDE_REASONING_MODEL': 'claude-opus-4-1-20250805'
    })
    @patch('app.utils.claude_client.Anthropic')
    def test_chat_completion_success(self, mock_anthropic_class, mock_claude_response):
        """chat_completion() 기본 메서드 테스트"""
        mock_client_instance = Mock()
        mock_anthropic_class.return_value = mock_client_instance
        mock_client_instance.messages.create.return_value = mock_claude_response

        client = ClaudeClient()
        messages = [{"role": "user", "content": "보고서를 작성하세요"}]

        response, input_tokens, output_tokens = client.chat_completion(messages)

        assert isinstance(response, str)
        assert len(response) > 0
        assert input_tokens == 1500
        assert output_tokens == 3200
        assert client.last_total_tokens == 4700

    @patch.dict('os.environ', {
        'CLAUDE_API_KEY': 'test_api_key',
        'CLAUDE_MODEL': 'claude-sonnet-4-5-20250929',
        'CLAUDE_FAST_MODEL': 'claude-haiku-4-5-20251001',
        'CLAUDE_REASONING_MODEL': 'claude-opus-4-1-20250805'
    })
    @patch('app.utils.claude_client.Anthropic')
    def test_chat_completion_fast_success(self, mock_anthropic_class, mock_fast_response):
        """chat_completion_fast() 빠른 모델 테스트"""
        mock_client_instance = Mock()
        mock_anthropic_class.return_value = mock_client_instance
        mock_client_instance.messages.create.return_value = mock_fast_response

        client = ClaudeClient()
        messages = [{"role": "user", "content": "개요를 작성하세요"}]

        response, input_tokens, output_tokens = client.chat_completion_fast(messages)

        # 빠른 모델 사용 확인
        assert isinstance(response, str)
        assert "요약" in response
        assert input_tokens == 800
        assert output_tokens == 150

    @patch.dict('os.environ', {
        'CLAUDE_API_KEY': 'test_api_key',
        'CLAUDE_MODEL': 'claude-sonnet-4-5-20250929',
        'CLAUDE_FAST_MODEL': 'claude-haiku-4-5-20251001',
        'CLAUDE_REASONING_MODEL': 'claude-opus-4-1-20250805'
    })
    @patch('app.utils.claude_client.Anthropic')
    def test_chat_completion_reasoning_success(self, mock_anthropic_class, mock_claude_response):
        """chat_completion_reasoning() 추론 모델 테스트"""
        mock_client_instance = Mock()
        mock_anthropic_class.return_value = mock_client_instance
        mock_client_instance.messages.create.return_value = mock_claude_response

        client = ClaudeClient()
        messages = [{"role": "user", "content": "복잡한 분석을 수행하세요"}]

        response, input_tokens, output_tokens = client.chat_completion_reasoning(messages)

        assert isinstance(response, str)
        assert input_tokens == 1500
        assert output_tokens == 3200

    @patch.dict('os.environ', {
        'CLAUDE_API_KEY': 'test_api_key',
        'CLAUDE_MODEL': 'claude-sonnet-4-5-20250929',
        'CLAUDE_FAST_MODEL': 'claude-haiku-4-5-20251001',
        'CLAUDE_REASONING_MODEL': 'claude-opus-4-1-20250805'
    })
    @patch('app.utils.claude_client.Anthropic')
    def test_chat_completion_with_custom_system_prompt(self, mock_anthropic_class, mock_claude_response):
        """커스텀 system_prompt 사용 테스트"""
        mock_client_instance = Mock()
        mock_anthropic_class.return_value = mock_client_instance
        mock_client_instance.messages.create.return_value = mock_claude_response

        client = ClaudeClient()
        messages = [{"role": "user", "content": "테스트"}]
        custom_prompt = "커스텀 시스템 프롬프트"

        response, input_tokens, output_tokens = client.chat_completion(
            messages, system_prompt=custom_prompt
        )

        # API 호출 시 커스텀 프롬프트가 전달되었는지 확인
        call_args = mock_client_instance.messages.create.call_args
        assert call_args.kwargs['system'] == custom_prompt

    @patch.dict('os.environ', {
        'CLAUDE_API_KEY': 'test_api_key',
        'CLAUDE_MODEL': 'claude-sonnet-4-5-20250929',
        'CLAUDE_FAST_MODEL': 'claude-haiku-4-5-20251001',
        'CLAUDE_REASONING_MODEL': 'claude-opus-4-1-20250805'
    })
    @patch('app.utils.claude_client.Anthropic')
    def test_models_loaded_correctly(self, mock_anthropic_class):
        """세 가지 모델이 올바르게 로드되었는지 테스트"""
        mock_client_instance = Mock()
        mock_anthropic_class.return_value = mock_client_instance

        client = ClaudeClient()

        # 각 모델 확인
        assert client.model == 'claude-sonnet-4-5-20250929'
        assert client.fast_model == 'claude-haiku-4-5-20251001'
        assert client.reasoning_model == 'claude-opus-4-1-20250805'

    @patch.dict('os.environ', {
        'CLAUDE_API_KEY': 'test_api_key',
        'CLAUDE_MODEL': 'claude-sonnet-4-5-20250929',
        'CLAUDE_FAST_MODEL': 'claude-haiku-4-5-20251001',
        'CLAUDE_REASONING_MODEL': 'claude-opus-4-1-20250805'
    })
    @patch('app.utils.claude_client.Anthropic')
    def test_token_tracking_across_methods(self, mock_anthropic_class, mock_claude_response):
        """모든 메서드에서 토큰 추적이 정상 작동하는지 테스트"""
        mock_client_instance = Mock()
        mock_anthropic_class.return_value = mock_client_instance
        mock_client_instance.messages.create.return_value = mock_claude_response

        client = ClaudeClient()
        messages = [{"role": "user", "content": "테스트"}]

        # chat_completion 호출
        client.chat_completion(messages)
        assert client.last_input_tokens == 1500
        assert client.last_output_tokens == 3200

        # chat_completion_fast 호출
        fast_response = Mock()
        fast_response.content = [Mock(text="빠른 응답")]
        fast_response.usage = Mock(input_tokens=500, output_tokens=100)
        mock_client_instance.messages.create.return_value = fast_response

        client.chat_completion_fast(messages)
        assert client.last_input_tokens == 500
        assert client.last_output_tokens == 100

    @patch.dict('os.environ', {
        'CLAUDE_API_KEY': 'test_api_key',
        'CLAUDE_MODEL': 'claude-sonnet-4-5-20250929',
        'CLAUDE_FAST_MODEL': 'claude-haiku-4-5-20251001',
        'CLAUDE_REASONING_MODEL': 'claude-opus-4-1-20250805'
    })
    @patch('app.utils.claude_client.Anthropic')
    def test_get_token_usage(self, mock_anthropic_class, mock_claude_response):
        """get_token_usage() 메서드 테스트"""
        mock_client_instance = Mock()
        mock_anthropic_class.return_value = mock_client_instance
        mock_client_instance.messages.create.return_value = mock_claude_response

        client = ClaudeClient()
        messages = [{"role": "user", "content": "테스트"}]

        client.chat_completion(messages)
        usage = client.get_token_usage()

        assert usage["input_tokens"] == 1500
        assert usage["output_tokens"] == 3200
        assert usage["total_tokens"] == 4700
