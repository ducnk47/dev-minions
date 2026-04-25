import pytest
from unittest.mock import MagicMock, patch
from minions.blueprint.engine import BlueprintEngine, EscalationError
from minions.blueprint.nodes import DeterministicNode, AgenticNode
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
    devbox.exec.return_value = MagicMock(stdout="ok", stderr="", returncode=0)
    return BlueprintContext(
        task="fix bug", repo_path="/tmp", partner="test",
        partner_config=config, devbox=devbox,
    )


def test_engine_runs_deterministic_node(mocker):
    ctx = _make_context()
    node = DeterministicNode(name="run_lint", command="eslint .", timeout=60, on_fail="warn")
    engine = BlueprintEngine([node])
    engine.run(ctx)
    ctx.devbox.exec.assert_called_once_with("eslint .", timeout=60)


def test_engine_aborts_on_deterministic_failure(mocker):
    ctx = _make_context()
    ctx.devbox.exec.return_value = MagicMock(stdout="", stderr="error", returncode=1)
    node = DeterministicNode(name="fail_node", command="bad_cmd", timeout=10, on_fail="abort")
    engine = BlueprintEngine([node])
    with pytest.raises(SystemExit):
        engine.run(ctx)


def test_engine_escalates_on_deterministic_failure(mocker):
    ctx = _make_context()
    ctx.devbox.exec.return_value = MagicMock(stdout="", stderr="error", returncode=1)
    node = DeterministicNode(name="fail_node", command="bad_cmd", timeout=10, on_fail="escalate")
    engine = BlueprintEngine([node])
    with pytest.raises(EscalationError):
        engine.run(ctx)


def test_engine_calls_agentic_node_handler(mocker):
    ctx = _make_context()
    node = AgenticNode(
        name="plan", system_prompt="plan prompt", tools=["bash"],
        max_tokens=1000, max_iterations=5, on_max_reached="escalate"
    )
    mock_run_agent = mocker.patch("minions.blueprint.engine.run_agent")
    mock_run_agent.return_value = MagicMock(done=True, output="done")
    engine = BlueprintEngine([node])
    engine.run(ctx)
    mock_run_agent.assert_called_once()


def test_engine_escalates_when_agent_exceeds_iterations(mocker):
    ctx = _make_context()
    node = AgenticNode(
        name="implement", system_prompt="impl prompt", tools=["bash"],
        max_tokens=1000, max_iterations=5, on_max_reached="escalate"
    )
    mock_run_agent = mocker.patch("minions.blueprint.engine.run_agent")
    mock_run_agent.return_value = MagicMock(done=False, reason="max_iterations_reached")
    engine = BlueprintEngine([node])
    with pytest.raises(EscalationError):
        engine.run(ctx)
