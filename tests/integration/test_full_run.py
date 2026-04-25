from __future__ import annotations
import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock
from minions.config import PartnerConfig
from minions.blueprint.context import BlueprintContext
from minions.blueprint.engine import BlueprintEngine
from minions.blueprint.standard import STANDARD_BLUEPRINT, NODE_HANDLERS
from minions.devbox.base import ExecResult

FIXTURE_REPO = Path(__file__).parent / "fixture_repo"

pytestmark = pytest.mark.skipif(
    os.environ.get("MINION_INTEGRATION") != "1",
    reason="Set MINION_INTEGRATION=1 to run integration tests (requires Docker + ANTHROPIC_API_KEY)"
)


@pytest.fixture
def partner_config():
    return PartnerConfig(
        partner="test", llm_provider="claude", model="claude-haiku-4-5-20251001",
        api_key_env="ANTHROPIC_API_KEY",
        devbox={"prefer_devcontainer": False, "language_fallback": "python"},
        commands={"lint": "ruff check .", "test": "pytest src/", "install": "pip install -e . -q"},
        blueprint="standard", tools=["bash"],
        rule_files={"global": ".cursorrules", "scoped": True},
        pr={"base_branch": "main", "risk_classification": True,
            "labels": {"robot": "minion:robot", "1-brain": "minion:1-brain",
                       "2-brain": "minion:2-brain", "3-brain": "minion:3-brain"}},
    )


def test_agent_can_plan_and_implement(partner_config):
    """
    End-to-end test: agent reads fixture repo, understands the divide() bug,
    and produces a fix. Does NOT push to git or create PR.
    Requires: Docker installed, ANTHROPIC_API_KEY set.
    """
    from minions.devbox.devcontainer import DevContainerDevbox

    devbox = DevContainerDevbox(
        repo_path=str(FIXTURE_REPO),
        language_fallback="python",
    )
    devbox.start()
    devbox.wait_until_ready()

    ctx = BlueprintContext(
        task=(
            "Fix the divide() function in src/math.py. "
            "Expected behavior: divide(1, 0) should raise ZeroDivisionError with a clear message. "
            "The function currently raises an unhandled exception. "
            "Steps to reproduce: run pytest src/test_math.py::test_divide_by_zero"
        ),
        repo_path=str(FIXTURE_REPO),
        partner="test",
        partner_config=partner_config,
        devbox=devbox,
    )

    # Only run plan + implement nodes (skip git/PR for integration test)
    from minions.blueprint.nodes import AgenticNode
    agentic_nodes = [n for n in STANDARD_BLUEPRINT if isinstance(n, AgenticNode) and n.name in ("plan", "implement")]
    engine = BlueprintEngine(nodes=agentic_nodes, node_handlers=NODE_HANDLERS)
    engine.run(ctx)

    # Verify agent touched the file
    result = devbox.exec("cat src/math.py")
    assert "0" in result.stdout or "zero" in result.stdout.lower() or "ZeroDivision" in result.stdout

    devbox.stop()
