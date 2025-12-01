import importlib
from unittest.mock import patch

import pytest

MODULE_PATH = "app.routers.topics"
LOGGER_INFO_PATH = f"{MODULE_PATH}.logger.info"


@pytest.fixture(scope="module")
def compose_system_prompt():
    module = importlib.import_module(MODULE_PATH)
    func = getattr(module, "_compose_system_prompt", None)
    if func is None:
        pytest.skip("_compose_system_prompt is not implemented yet")
    return func


def _assert_log(mock_logger, user_len: int, system_len: int, total_len: int):
    mock_logger.assert_called_once()
    log_message = mock_logger.call_args.args[0]
    expected = (
        "[COMPOSE_PROMPT] Composed system prompt - "
        f"user_part={user_len}B, system_part={system_len}B, total={total_len}B"
    )
    assert log_message == expected


# TC-001: join user + system prompts with delimiter and log lengths.
def test_compose_prompt_both_parts(compose_system_prompt):

    user_part = "Step 1 planning"
    system_part = "Rules: Follow format X"
    expected = f"{user_part}\n\n{system_part}"

    with patch(LOGGER_INFO_PATH) as mock_info:
        result = compose_system_prompt(user_part, system_part)

    assert result == expected
    assert len(result) == len(expected)
    assert result.count("\n\n") == 1
    _assert_log(mock_info, len(user_part), len(system_part), len(expected))


# TC-002: only user prompt should survive and log system length as zero.
def test_compose_prompt_user_only(compose_system_prompt):

    user_part = "Step 1"

    with patch(LOGGER_INFO_PATH) as mock_info:
        result = compose_system_prompt(user_part, None)

    assert result == user_part
    assert len(result) == len(user_part)
    _assert_log(mock_info, len(user_part), 0, len(user_part))


# TC-003: only system prompt should survive and log user length as zero.
def test_compose_prompt_system_only(compose_system_prompt):

    system_part = "Rules: X"

    with patch(LOGGER_INFO_PATH) as mock_info:
        result = compose_system_prompt(None, system_part)

    assert result == system_part
    assert len(result) == len(system_part)
    _assert_log(mock_info, 0, len(system_part), len(system_part))


# TC-004: returning None when both inputs are None.
def test_compose_prompt_both_none(compose_system_prompt):

    with patch(LOGGER_INFO_PATH) as mock_info:
        result = compose_system_prompt(None, None)

    assert result is None
    mock_info.assert_called_once()
    _assert_log(mock_info, 0, 0, 0)


# TC-005: whitespace-only user prompt should be ignored.
def test_compose_prompt_trimmed_user(compose_system_prompt):

    system_part = "Rules: X"
    result = compose_system_prompt("  ", system_part)

    assert result == system_part
    assert len(result) == len(system_part)
    assert "\n\n" not in result


# TC-006: both whitespace-only inputs should yield None.
def test_compose_prompt_both_whitespace(compose_system_prompt):

    result = compose_system_prompt("  ", "   ")

    assert result is None
