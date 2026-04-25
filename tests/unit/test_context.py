from unittest.mock import MagicMock
from minions.blueprint.context import BlueprintContext
from minions.config import PartnerConfig

def _make_config():
    return PartnerConfig(
        partner="test", llm_provider="claude", model="claude-sonnet-4-6",
        api_key_env="ANTHROPIC_API_KEY",
        devbox={"prefer_devcontainer": True, "language_fallback": "node"},
        commands={"lint": "eslint .", "test": "npm test", "install": "npm install"},
        blueprint="standard", tools=["bash"],
        rule_files={"global": ".cursorrules", "scoped": True},
        pr={"base_branch": "main", "risk_classification": True, "labels": {}},
    )

def test_context_initializes():
    ctx = BlueprintContext(
        task="fix the bug",
        repo_path="/tmp/repo",
        partner="test",
        partner_config=_make_config(),
        devbox=MagicMock(),
    )
    assert ctx.task == "fix the bug"
    assert ctx.conversation_history == []
    assert ctx.artifacts == {}
    assert ctx.escalation_reason is None

def test_context_add_artifact():
    ctx = BlueprintContext(
        task="fix", repo_path="/tmp", partner="test",
        partner_config=_make_config(), devbox=MagicMock(),
    )
    ctx.artifacts["pr_url"] = "https://github.com/x/y/pull/1"
    assert ctx.artifacts["pr_url"] == "https://github.com/x/y/pull/1"
