from __future__ import annotations
from minions.devbox.base import Devbox
from minions.config import PartnerConfig


class PreflightError(Exception):
    pass


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
