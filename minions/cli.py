from __future__ import annotations
import sys
from pathlib import Path
import typer
from rich.console import Console
from rich.panel import Panel

from minions.config import load_partner_config
from minions.blueprint.context import BlueprintContext
from minions.blueprint.engine import BlueprintEngine, EscalationError
from minions.blueprint.standard import STANDARD_BLUEPRINT, NODE_HANDLERS

app = typer.Typer(help="dev-box-minions — autonomous coding agent")
console = Console()


@app.command()
def run(
    task: str = typer.Option(..., "--task", "-t", help="Task description"),
    repo: str = typer.Option(..., "--repo", "-r", help="Path to the target repository"),
    partner: str = typer.Option("default", "--partner", "-p", help="Partner config name"),
    config_dir: str = typer.Option("configs/partners", "--config-dir", help="Directory containing partner configs"),
):
    """Run a minion on a task."""
    config_path = Path(config_dir) / f"{partner}.yml"

    try:
        partner_config = load_partner_config(config_path)
    except FileNotFoundError:
        console.print(f"[red]Partner config not found: {config_path}[/red]")
        raise typer.Exit(1)
    except ValueError as e:
        console.print(f"[red]Invalid partner config: {e}[/red]")
        raise typer.Exit(1)

    console.print(Panel(
        f"[bold]Task:[/bold] {task}\n"
        f"[bold]Repo:[/bold] {repo}\n"
        f"[bold]Partner:[/bold] {partner} ({partner_config.model})",
        title="Minion Starting",
        border_style="blue",
    ))

    ctx = BlueprintContext(
        task=task,
        repo_path=repo,
        partner=partner,
        partner_config=partner_config,
        devbox=None,  # boot_devbox handler sets this
    )

    engine = BlueprintEngine(nodes=STANDARD_BLUEPRINT, node_handlers=NODE_HANDLERS)

    try:
        engine.run(ctx)
    except EscalationError as e:
        _print_escalation(e, ctx)
        raise typer.Exit(2)
    except SystemExit as e:
        raise typer.Exit(e.code)


def _print_escalation(error: EscalationError, ctx: BlueprintContext) -> None:
    tried = "\n  ".join(
        f"{i+1}. {msg}"
        for i, msg in enumerate(ctx.artifacts.get("attempts", []))
    ) or "  (no attempts recorded)"

    branch = ctx.artifacts.get("branch", "not yet pushed")
    last_output = ctx.artifacts.get("last_test_output", "")[-2000:]

    console.print(Panel(
        f"[bold red]Stage:[/bold red]    {error.stage}\n"
        f"[bold red]Reason:[/bold red]   {error.reason}\n\n"
        f"[bold]What was tried:[/bold]\n  {tried}\n\n"
        f"[bold]Branch:[/bold] {branch}\n\n"
        + (f"[bold]Last output:[/bold]\n{last_output}" if last_output else ""),
        title="ESCALATION REQUIRED",
        border_style="red",
    ))
