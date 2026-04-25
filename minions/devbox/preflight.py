from __future__ import annotations
import subprocess
from minions.devbox.base import Devbox
from minions.config import PartnerConfig


class PreflightError(Exception):
    pass


def check_host_prerequisites() -> None:
    """Check host-level prerequisites before booting the devbox. Raises PreflightError fast."""
    # Docker running?
    r = subprocess.run(["docker", "info"], capture_output=True, timeout=10)
    if r.returncode != 0:
        raise PreflightError(
            "Docker is not running. Start Docker Desktop (or run: sudo systemctl start docker) and try again."
        )

    # devcontainer CLI installed?
    r = subprocess.run(["devcontainer", "--version"], capture_output=True, timeout=10)
    if r.returncode != 0:
        raise PreflightError(
            "devcontainer CLI not found. Install it with: npm install -g @devcontainers/cli"
        )


def run_preflight_checks(devbox: Devbox, config: PartnerConfig) -> None:
    checks = [
        ("git remote",    "git remote -v",                                  "git remote not accessible"),
        ("gh auth",       "gh auth status",                                 "gh CLI not authenticated — run: gh auth login"),
        ("install",       config.commands["install"],                       f"dependency install failed: {config.commands['install']}"),
        ("lint tool",     f"which {config.commands['lint'].split()[0]}",    f"lint tool not found: {config.commands['lint'].split()[0]}"),
        ("test runner",   f"which {config.commands['test'].split()[0]}",    f"test runner not found: {config.commands['test'].split()[0]}"),
    ]

    for check_name, command, error_msg in checks:
        result = devbox.exec(command, timeout=60)
        if not result.ok:
            raise PreflightError(
                f"Pre-flight check failed [{check_name}]: {error_msg}\n"
                f"Output: {result.stderr or result.stdout}"
            )
