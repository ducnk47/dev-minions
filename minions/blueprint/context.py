from __future__ import annotations
from dataclasses import dataclass, field
from minions.config import PartnerConfig


@dataclass
class BlueprintContext:
    task: str
    repo_path: str
    partner: str
    partner_config: PartnerConfig
    devbox: object                          # Devbox instance (avoids circular import)
    conversation_history: list = field(default_factory=list)
    artifacts: dict = field(default_factory=dict)
    escalation_reason: str | None = None
