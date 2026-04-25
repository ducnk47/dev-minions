from __future__ import annotations
import sys
import re
import datetime
from pathlib import Path
from minions.blueprint.nodes import DeterministicNode, AgenticNode
from minions.blueprint.context import BlueprintContext
from minions.blueprint.prompts import PLAN_PROMPT, IMPL_PROMPT, FIX_PROMPT
from minions.blueprint.risk import classify_pr_risk
from minions.devbox.preflight import run_preflight_checks, check_host_prerequisites, PreflightError
from minions.qualify.task import qualify_task
from minions.rules.loader import load_rules_for_paths


def _boot_devbox_handler(ctx: BlueprintContext) -> None:
    try:
        check_host_prerequisites()
    except PreflightError as e:
        print(f"\n[ABORT] {e}", file=sys.stderr)
        sys.exit(1)

    from minions.devbox.devcontainer import DevContainerDevbox
    try:
        devbox = DevContainerDevbox(
            repo_path=ctx.repo_path,
            language_fallback=ctx.partner_config.devbox.get("language_fallback", "node"),
        )
        devbox.start()
        devbox.wait_until_ready()
    except RuntimeError as e:
        print(f"\n[ABORT] Failed to boot devbox: {e}", file=sys.stderr)
        sys.exit(1)
    ctx.devbox = devbox


def _preflight_handler(ctx: BlueprintContext) -> None:
    try:
        run_preflight_checks(ctx.devbox, ctx.partner_config)
    except PreflightError as e:
        print(f"\n[ABORT] {e}", file=sys.stderr)
        sys.exit(1)


def _qualify_handler(ctx: BlueprintContext) -> None:
    from minions.blueprint.engine import EscalationError
    result = qualify_task(ctx.task)
    if not result.qualified:
        ctx.escalation_reason = result.escalation_message
        raise EscalationError("qualify_task", result.escalation_message, ctx)


def _hydrate_context_handler(ctx: BlueprintContext) -> None:
    from minions.rules.loader import load_rules_for_paths
    from minions.skills.loader import select_skill_for_task, load_skill_content

    rules = load_rules_for_paths(Path(ctx.repo_path), [])
    ctx.artifacts["rules"] = rules

    skill_name = select_skill_for_task(ctx.task)
    ctx.artifacts["skill_name"] = skill_name
    ctx.artifacts["skill"] = load_skill_content(skill_name)


def _risk_classify_handler(ctx: BlueprintContext) -> None:
    result = ctx.devbox.exec(
        "git diff --name-only HEAD && git diff --stat HEAD | tail -1",
        timeout=15
    )
    files = [l for l in result.stdout.splitlines() if l.strip() and not l.startswith(" ")]
    lines_match = [l for l in result.stdout.splitlines() if "changed" in l]
    lines = 0
    if lines_match:
        nums = re.findall(r'\d+', lines_match[-1])
        lines = sum(int(n) for n in nums)

    tier = classify_pr_risk(files_changed=files, lines_changed=lines)
    ctx.artifacts["risk_tier"] = tier
    ctx.artifacts["pr_label"] = ctx.partner_config.pr["labels"].get(tier, tier)


def _create_pr_handler(ctx: BlueprintContext) -> None:
    label = ctx.artifacts.get("pr_label", "minion:1-brain")
    base = ctx.partner_config.pr.get("base_branch", "main")

    result = ctx.devbox.exec(
        f'gh pr create --title "minion: {ctx.task[:60]}" '
        f'--body "Automated PR by dev-box-minions\n\nTask: {ctx.task}" '
        f'--base {base} --label "{label}"',
        timeout=30,
    )
    if result.ok:
        pr_url = result.stdout.strip().splitlines()[-1]
        ctx.artifacts["pr_url"] = pr_url


def _report_handler(ctx: BlueprintContext) -> None:
    from rich.console import Console
    from rich.panel import Panel
    console = Console()
    tier = ctx.artifacts.get("risk_tier", "unknown")
    pr_url = ctx.artifacts.get("pr_url", "PR URL not available")
    console.print(Panel(
        f"[green]✓ PR created:[/green] {pr_url}\n"
        f"[blue]Risk tier:[/blue] {tier}\n"
        f"[dim]Task: {ctx.task}[/dim]",
        title="Minion Complete",
        border_style="green",
    ))


GIT_PUSH_CMD = (
    "git config user.email 'minion@dev-box-minions' && "
    "git config user.name 'Minion' && "
    "git checkout -b minion/$(date +%Y%m%d-%H%M%S)-task 2>/dev/null || true && "
    "git add -A && "
    "git diff --cached --quiet || git commit -m 'feat: minion changes' && "
    "git push origin HEAD"
)

STANDARD_BLUEPRINT = [
    DeterministicNode("boot_devbox",      command=None,                            timeout=120, on_fail="abort"),
    DeterministicNode("pre_flight_check", command=None,                            timeout=30,  on_fail="abort"),
    DeterministicNode("qualify_task",     command=None,                            timeout=10,  on_fail="escalate"),
    DeterministicNode("hydrate_context",  command=None,                            timeout=10,  on_fail="warn"),
    AgenticNode      ("plan",             system_prompt=PLAN_PROMPT,               tools=["bash"], max_tokens=4096, max_iterations=10,  on_max_reached="escalate"),
    AgenticNode      ("implement",        system_prompt=IMPL_PROMPT,               tools=["bash"], max_tokens=8192, max_iterations=30,  on_max_reached="escalate"),
    DeterministicNode("lint_autofix",     command="{lint} 2>/dev/null || true",    timeout=60,  on_fail="warn",    autofix=True),
    DeterministicNode("run_tests",        command="{test}",                        timeout=300, on_fail="continue"),
    AgenticNode      ("fix_failures",     system_prompt=FIX_PROMPT,               tools=["bash"], max_tokens=4096, max_iterations=15,  on_max_reached="escalate"),
    DeterministicNode("git_push",         command=GIT_PUSH_CMD,                   timeout=60,  on_fail="abort"),
    DeterministicNode("risk_classify_pr", command=None,                            timeout=10,  on_fail="warn"),
    DeterministicNode("create_pr",        command=None,                            timeout=30,  on_fail="abort"),
    DeterministicNode("report",           command=None,                            timeout=5,   on_fail="warn"),
]

NODE_HANDLERS = {
    "boot_devbox":      _boot_devbox_handler,
    "pre_flight_check": _preflight_handler,
    "qualify_task":     _qualify_handler,
    "hydrate_context":  _hydrate_context_handler,
    "risk_classify_pr": _risk_classify_handler,
    "create_pr":        _create_pr_handler,
    "report":           _report_handler,
}
