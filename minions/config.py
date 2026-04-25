from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import yaml


@dataclass
class PartnerConfig:
    partner: str
    llm_provider: str
    model: str
    api_key_env: str
    devbox: dict
    commands: dict
    blueprint: str
    tools: list[str]
    rule_files: dict
    pr: dict


def load_partner_config(path: Path) -> PartnerConfig:
    if not path.exists():
        raise FileNotFoundError(f"Partner config not found: {path}")

    with open(path) as f:
        data = yaml.safe_load(f)

    required = ["partner", "llm_provider", "model", "api_key_env",
                "devbox", "commands", "blueprint", "tools", "rule_files", "pr"]
    missing = [field for field in required if field not in data]
    if missing:
        raise ValueError(f"Partner config missing required fields: {missing}")

    return PartnerConfig(**{k: data[k] for k in required})
