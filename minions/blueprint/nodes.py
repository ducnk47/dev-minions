from __future__ import annotations
from dataclasses import dataclass, field

_DET_ON_FAIL = {"abort", "warn", "escalate", "continue"}
_AG_ON_MAX = {"abort", "escalate"}


@dataclass
class DeterministicNode:
    name: str
    command: str | None
    timeout: int
    on_fail: str
    autofix: bool = False

    def __post_init__(self):
        if self.on_fail not in _DET_ON_FAIL:
            raise ValueError(f"on_fail must be one of {_DET_ON_FAIL}, got '{self.on_fail}'")


@dataclass
class AgenticNode:
    name: str
    system_prompt: str
    tools: list[str]
    max_tokens: int
    max_iterations: int
    on_max_reached: str

    def __post_init__(self):
        if self.on_max_reached not in _AG_ON_MAX:
            raise ValueError(f"on_max_reached must be one of {_AG_ON_MAX}, got '{self.on_max_reached}'")
