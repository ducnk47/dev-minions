import pytest
from unittest.mock import MagicMock, patch
from minions.agent.runtime import run_agent, AgentResult
from minions.blueprint.context import BlueprintContext
from minions.config import PartnerConfig


def _make_context():
    config = PartnerConfig(
        partner="test", llm_provider="claude", model="claude-sonnet-4-6",
        api_key_env="ANTHROPIC_API_KEY",
        devbox={"prefer_devcontainer": True, "language_fallback": "node"},
        commands={"lint": "eslint .", "test": "npm test", "install": "npm install"},
        blueprint="standard", tools=["bash"],
        rule_files={"global": ".cursorrules", "scoped": True},
        pr={"base_branch": "main", "risk_classification": True, "labels": {}},
    )
    devbox = MagicMock()
    devbox.exec.return_value = MagicMock(stdout="file contents", stderr="", returncode=0)
    return BlueprintContext(task="fix bug", repo_path="/tmp", partner="test",
                            partner_config=config, devbox=devbox)


def test_agent_returns_done_when_no_tool_calls(mocker):
    ctx = _make_context()

    mock_response = MagicMock()
    mock_response.choices[0].message.tool_calls = None
    mock_response.choices[0].message.content = "I have completed the task."

    mocker.patch("litellm.completion", return_value=mock_response)

    result = run_agent("do the task", ["bash"], ctx, max_iterations=5)
    assert result.done is True
    assert result.output == "I have completed the task."


def test_agent_executes_bash_tool_call(mocker):
    ctx = _make_context()

    tool_call = MagicMock()
    tool_call.id = "call_123"
    tool_call.function.name = "bash"
    tool_call.function.arguments = '{"command": "cat src/auth.py"}'

    first_response = MagicMock()
    first_response.choices[0].message.tool_calls = [tool_call]
    first_response.choices[0].message.content = None

    done_response = MagicMock()
    done_response.choices[0].message.tool_calls = None
    done_response.choices[0].message.content = "Done."

    mocker.patch("litellm.completion", side_effect=[first_response, done_response])

    result = run_agent("fix the null check", ["bash"], ctx, max_iterations=5)
    assert result.done is True
    ctx.devbox.exec.assert_called_once_with("cat src/auth.py", timeout=30)


def test_agent_returns_not_done_at_max_iterations(mocker):
    ctx = _make_context()

    tool_call = MagicMock()
    tool_call.id = "call_x"
    tool_call.function.name = "bash"
    tool_call.function.arguments = '{"command": "echo hi"}'

    response = MagicMock()
    response.choices[0].message.tool_calls = [tool_call]
    response.choices[0].message.content = None

    mocker.patch("litellm.completion", return_value=response)

    result = run_agent("loop forever", ["bash"], ctx, max_iterations=3)
    assert result.done is False
    assert result.reason == "max_iterations_reached"
