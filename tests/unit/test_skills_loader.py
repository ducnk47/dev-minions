from pathlib import Path
from minions.skills.loader import select_skill_for_task, load_skill_content


def test_debug_keywords_select_debugging_skill():
    assert select_skill_for_task("fix the null pointer bug") == "debugging"
    assert select_skill_for_task("investigate why tests crash") == "debugging"


def test_implementation_keywords_select_implement_skill():
    assert select_skill_for_task("implement OAuth flow") == "implement-feature"
    assert select_skill_for_task("add a new endpoint") == "implement-feature"


def test_migration_keywords_select_migration_skill():
    assert select_skill_for_task("migrate all endpoints to v2") == "migration"
    assert select_skill_for_task("refactor the config module") == "migration"


def test_unknown_task_returns_default():
    assert select_skill_for_task("do the thing") == "implement-feature"


def test_load_skill_content_from_local_skills_dir(tmp_path, monkeypatch):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "debugging.md").write_text("# Debugging\nReproduce first.")
    monkeypatch.setenv("MINION_SKILLS_DIR", str(skills_dir))

    content = load_skill_content("debugging")
    assert "Reproduce first" in content


def test_load_skill_content_missing_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("MINION_SKILLS_DIR", str(tmp_path))  # empty dir
    assert load_skill_content("nonexistent") == ""
