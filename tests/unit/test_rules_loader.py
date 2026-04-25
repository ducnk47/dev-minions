from pathlib import Path
from minions.rules.loader import load_rules_for_paths


def test_loads_global_cursorrules(tmp_path):
    (tmp_path / ".cursorrules").write_text("Always use TypeScript strict mode.")
    rules = load_rules_for_paths(tmp_path, [tmp_path / "src" / "auth.ts"])
    assert "TypeScript strict mode" in rules


def test_loads_claude_md(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("Use pytest for tests.")
    rules = load_rules_for_paths(tmp_path, [tmp_path / "src" / "auth.py"])
    assert "pytest" in rules


def test_loads_agents_md(tmp_path):
    (tmp_path / "AGENTS.md").write_text("Avoid circular imports.")
    rules = load_rules_for_paths(tmp_path, [tmp_path / "main.py"])
    assert "circular imports" in rules


def test_loads_multiple_formats_in_same_repo(tmp_path):
    (tmp_path / ".cursorrules").write_text("cursor rule")
    (tmp_path / "CLAUDE.md").write_text("claude rule")
    rules = load_rules_for_paths(tmp_path, [tmp_path / "main.py"])
    assert "cursor rule" in rules
    assert "claude rule" in rules


def test_loads_scoped_cursorrules(tmp_path):
    (tmp_path / ".cursorrules").write_text("global rule")
    scoped_dir = tmp_path / "src" / "auth"
    scoped_dir.mkdir(parents=True)
    (scoped_dir / ".cursorrules").write_text("auth domain rule")
    rules = load_rules_for_paths(tmp_path, [scoped_dir / "service.ts"])
    assert "global rule" in rules
    assert "auth domain rule" in rules


def test_no_rule_files_returns_empty(tmp_path):
    rules = load_rules_for_paths(tmp_path, [tmp_path / "src" / "foo.ts"])
    assert rules == ""
