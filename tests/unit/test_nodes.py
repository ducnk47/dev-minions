import pytest
from minions.blueprint.nodes import DeterministicNode, AgenticNode

def test_deterministic_node_defaults():
    node = DeterministicNode(
        name="run_tests",
        command="npm test",
        timeout=300,
        on_fail="continue",
    )
    assert node.autofix is False
    assert node.on_fail == "continue"

def test_deterministic_node_invalid_on_fail():
    with pytest.raises(ValueError, match="on_fail"):
        DeterministicNode(name="x", command="x", timeout=10, on_fail="invalid")

def test_agentic_node_defaults():
    node = AgenticNode(
        name="plan",
        system_prompt="You are a coding agent.",
        tools=["bash"],
        max_tokens=4096,
        max_iterations=10,
        on_max_reached="escalate",
    )
    assert node.on_max_reached == "escalate"

def test_agentic_node_invalid_on_max_reached():
    with pytest.raises(ValueError, match="on_max_reached"):
        AgenticNode(
            name="x", system_prompt="x", tools=[],
            max_tokens=100, max_iterations=5, on_max_reached="invalid"
        )
