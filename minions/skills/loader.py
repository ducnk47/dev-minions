from __future__ import annotations
import os
import glob
from pathlib import Path

_SKILL_KEYWORDS = [
    (("fix", "bug", "error", "fail", "crash", "broken", "null pointer", "exception"), "debugging"),
    (("migrate", "refactor", "rename", "move", "port"),                                "migration"),
    (("test", "flaky", "spec", "failing test"),                                        "testing"),
    (("implement", "add", "build", "create", "new endpoint", "new feature"),           "implement-feature"),
]

DEFAULT_SKILL = "implement-feature"


def select_skill_for_task(task: str) -> str:
    task_lower = task.lower()
    for keywords, skill in _SKILL_KEYWORDS:
        if any(kw in task_lower for kw in keywords):
            return skill
    return DEFAULT_SKILL


def load_skill_content(skill_name: str) -> str:
    search_paths = []

    env_dir = os.environ.get("MINION_SKILLS_DIR")
    if env_dir:
        search_paths.append(Path(env_dir))

    search_paths.append(Path.cwd() / "skills")
    search_paths.append(Path.home() / ".claude" / "plugins" / "cache")

    for base in search_paths:
        if not base.exists():
            continue
        direct = base / f"{skill_name}.md"
        if direct.exists():
            return direct.read_text()
        matches = glob.glob(str(base / "**" / f"{skill_name}.md"), recursive=True)
        if matches:
            return Path(matches[0]).read_text()

    return ""
