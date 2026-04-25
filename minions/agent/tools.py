from __future__ import annotations
import json
from minions.devbox.base import ExecResult

BASH_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "bash",
        "description": (
            "Execute a shell command in the devbox. Returns stdout + stderr. "
            "Use this to read files (cat), write files (tee), search code (rg), "
            "run tests, git operations, and any other shell task."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute.",
                }
            },
            "required": ["command"],
        },
    },
}

TOOL_SCHEMAS = {"bash": BASH_TOOL_SCHEMA}


def execute_tool(tool_call, devbox) -> dict:
    name = tool_call.function.name
    args = json.loads(tool_call.function.arguments)

    if name == "bash":
        result: ExecResult = devbox.exec(args["command"], timeout=30)
        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]: {result.stderr}"
        if not result.ok:
            output += f"\n[exit code]: {result.returncode}"
        return {"tool_call_id": tool_call.id, "role": "tool", "content": output or "(empty output)"}

    return {"tool_call_id": tool_call.id, "role": "tool", "content": f"Unknown tool: {name}"}
