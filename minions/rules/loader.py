from __future__ import annotations
from pathlib import Path

RULE_FILENAMES = [
    ".cursorrules",
    "CLAUDE.md",
    "AGENTS.md",
]


def load_rules_for_paths(repo_root: Path, file_paths: list[Path]) -> str:
    seen_files: set[Path] = set()
    rules_parts: list[str] = []

    def _try_load(directory: Path) -> None:
        for filename in RULE_FILENAMES:
            rules_file = directory / filename
            if rules_file in seen_files:
                continue
            if rules_file.exists():
                seen_files.add(rules_file)
                content = rules_file.read_text().strip()
                if content:
                    rel = rules_file.relative_to(repo_root)
                    rules_parts.append(f"# {rel}\n{content}")

    _try_load(repo_root)

    for file_path in file_paths:
        current = file_path.parent
        while repo_root in current.parents or current == repo_root:
            _try_load(current)
            if current == repo_root:
                break
            current = current.parent

    return "\n\n".join(rules_parts)
