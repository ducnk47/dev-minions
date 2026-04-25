from __future__ import annotations
import sys
from minions.blueprint.nodes import DeterministicNode, AgenticNode
from minions.blueprint.context import BlueprintContext
from minions.agent.runtime import run_agent


class EscalationError(Exception):
    def __init__(self, stage: str, reason: str, context: BlueprintContext):
        self.stage = stage
        self.reason = reason
        self.context = context
        super().__init__(f"Escalation at '{stage}': {reason}")


class BlueprintEngine:
    def __init__(self, nodes: list, node_handlers: dict = None):
        self.nodes = nodes
        self.node_handlers = node_handlers or {}

    def run(self, ctx: BlueprintContext) -> None:
        for node in self.nodes:
            if isinstance(node, DeterministicNode):
                self._run_deterministic(node, ctx)
            elif isinstance(node, AgenticNode):
                self._run_agentic(node, ctx)

    def _run_deterministic(self, node: DeterministicNode, ctx: BlueprintContext) -> None:
        if node.command is None:
            handler = self.node_handlers.get(node.name)
            if handler:
                handler(ctx)
            return

        command = node.command.format(
            lint=ctx.partner_config.commands.get("lint", "true"),
            test=ctx.partner_config.commands.get("test", "true"),
        )

        result = ctx.devbox.exec(command, timeout=node.timeout)

        if result.returncode != 0:
            if node.on_fail == "abort":
                print(f"\n[ABORT] Node '{node.name}' failed:\n{result.stderr}", file=sys.stderr)
                sys.exit(1)
            elif node.on_fail == "escalate":
                ctx.escalation_reason = f"Node '{node.name}' failed: {result.stderr}"
                raise EscalationError(node.name, ctx.escalation_reason, ctx)
            elif node.on_fail == "warn":
                print(f"[WARN] Node '{node.name}' failed (continuing): {result.stderr}")
            # "continue" — silent

    def _run_agentic(self, node: AgenticNode, ctx: BlueprintContext) -> None:
        # Prepend loaded rules and skill to the node's system prompt if present
        rules = ctx.artifacts.get("rules", "")
        skill = ctx.artifacts.get("skill", "")

        prefix_parts = []
        if rules:
            prefix_parts.append(f"# Repository Rules\n{rules}")
        if skill:
            prefix_parts.append(f"# Task Approach\n{skill}")

        if prefix_parts:
            system_prompt = "\n\n".join(prefix_parts) + "\n\n---\n\n" + node.system_prompt
        else:
            system_prompt = node.system_prompt

        result = run_agent(
            system_prompt=system_prompt,
            tool_names=node.tools,
            context=ctx,
            max_iterations=node.max_iterations,
        )

        if not result.done:
            if node.on_max_reached == "escalate":
                ctx.escalation_reason = f"Agent '{node.name}' hit max iterations: {result.reason}"
                raise EscalationError(node.name, ctx.escalation_reason, ctx)
            else:
                print(f"\n[ABORT] Agent '{node.name}' hit max iterations.", file=sys.stderr)
                sys.exit(1)

        ctx.conversation_history = result.messages
