from __future__ import annotations
import json
import shutil
import subprocess
from pathlib import Path
from minions.devbox.base import Devbox, ExecResult

TEMPLATES_DIR = Path(__file__).parent / "templates"
AGENT_PACKAGES = ["ripgrep", "jq"]


class DevContainerDevbox(Devbox):
    def __init__(self, repo_path: str, language_fallback: str = "node"):
        self.repo_path = Path(repo_path)
        self.language_fallback = language_fallback
        self._workspace: Path = self.repo_path
        self._ensure_devcontainer_config()

    def _ensure_devcontainer_config(self) -> None:
        dc_dir = self.repo_path / ".devcontainer"
        if dc_dir.exists():
            return  # use repo's own config

        dc_dir.mkdir(exist_ok=True)
        template = TEMPLATES_DIR / f"{self.language_fallback}.json"
        if not template.exists():
            template = TEMPLATES_DIR / "node.json"
        shutil.copy(template, dc_dir / "devcontainer.json")

    def start(self) -> None:
        result = subprocess.run(
            ["devcontainer", "up", "--workspace-folder", str(self.repo_path)],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(f"devcontainer up failed:\n{result.stderr}")

    def wait_until_ready(self) -> None:
        # devcontainer up is synchronous — postCreateCommand completes before it returns
        # Install agent tools on top
        for pkg in AGENT_PACKAGES:
            self.exec(f"which {pkg} || (apt-get update -qq && apt-get install -y -qq {pkg})", timeout=60)

    def exec(self, command: str, timeout: int = 60) -> ExecResult:
        result = subprocess.run(
            [
                "devcontainer", "exec",
                "--workspace-folder", str(self.repo_path),
                "--", "bash", "-c", command,
            ],
            capture_output=True, text=True, timeout=timeout,
        )
        return ExecResult(
            stdout=result.stdout,
            stderr=result.stderr,
            returncode=result.returncode,
        )

    def stop(self) -> None:
        # Dev Containers are stopped by removing the container
        subprocess.run(
            ["devcontainer", "down", "--workspace-folder", str(self.repo_path)],
            capture_output=True,
        )
