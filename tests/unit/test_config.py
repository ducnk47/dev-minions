import pytest
from pathlib import Path
from minions.config import PartnerConfig, load_partner_config

def test_load_default_config(tmp_path):
    cfg_file = tmp_path / "client.yml"
    cfg_file.write_text("""
partner: test_client
llm_provider: claude
model: claude-sonnet-4-6
api_key_env: ANTHROPIC_API_KEY
devbox:
  prefer_devcontainer: true
  language_fallback: node
commands:
  lint: "eslint . --ext .js,.ts"
  test: "npm test"
  install: "npm install"
blueprint: standard
tools:
  - bash
rule_files:
  global: ".cursorrules"
  scoped: true
pr:
  base_branch: main
  risk_classification: true
  labels:
    robot: "minion:robot"
    1-brain: "minion:1-brain"
    2-brain: "minion:2-brain"
    3-brain: "minion:3-brain"
""")
    config = load_partner_config(cfg_file)
    assert config.partner == "test_client"
    assert config.model == "claude-sonnet-4-6"
    assert config.commands["test"] == "npm test"
    assert config.pr["base_branch"] == "main"
    assert config.devbox["prefer_devcontainer"] is True

def test_missing_required_field(tmp_path):
    cfg_file = tmp_path / "bad.yml"
    cfg_file.write_text("partner: test_client\n")
    with pytest.raises(ValueError, match="model"):
        load_partner_config(cfg_file)

def test_config_not_found():
    with pytest.raises(FileNotFoundError):
        load_partner_config(Path("/nonexistent/path.yml"))
