from __future__ import annotations
import os
from dataclasses import dataclass, field
import litellm
from minions.agent.tools import TOOL_SCHEMAS, execute_tool
from minions.blueprint.context import BlueprintContext


@dataclass
class AgentResult:
    done: bool
    output: str = ""
    reason: str = ""
    messages: list = field(default_factory=list)


def run_agent(
    system_prompt: str,
    tool_names: list[str],
    context: BlueprintContext,
    max_iterations: int,
) -> AgentResult:
    os.environ.setdefault(
        context.partner_config.api_key_env,
        os.environ.get(context.partner_config.api_key_env, ""),
    )

    tools = [TOOL_SCHEMAS[name] for name in tool_names if name in TOOL_SCHEMAS]
    messages = list(context.conversation_history)
    messages.append({"role": "user", "content": system_prompt})

    for _ in range(max_iterations):
        response = litellm.completion(
            model=context.partner_config.model,
            messages=messages,
            tools=tools if tools else None,
        )

        msg = response.choices[0].message
        tool_calls = msg.tool_calls

        if not tool_calls:
            messages.append({"role": "assistant", "content": msg.content})
            return AgentResult(done=True, output=msg.content or "", messages=messages)

        messages.append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in tool_calls
            ],
        })

        for tc in tool_calls:
            tool_result = execute_tool(tc, context.devbox)
            messages.append(tool_result)

    return AgentResult(done=False, reason="max_iterations_reached", messages=messages)
