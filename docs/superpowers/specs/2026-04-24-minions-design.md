# dev-box-minions — Technical Design Spec

> Date: 2026-04-24
> Status: Approved for V1 implementation
> Context: Stripe Minions-inspired autonomous coding agent system for an outsourcing company

---

## Problem Statement

An outsourcing company manages multiple client codebases across different tech stacks, each with its own CI/CD pipeline. Developer attention is the scarcest resource. The goal is to automate end-to-end ticket-to-PR workflows so engineers spend time on review and judgment, not on mechanical implementation.

**Constraints:**
- Multi-repo, multi-partner: each client has a different codebase, stack, and CI
- No single shared infrastructure: per-partner CI/CD, per-partner rule sets
- MVP must be research-grade: prove the pipeline before scaling
- Must not compromise code quality entering production systems

---

## Architecture Overview

```
CLI Entry Point
    minion run --task "..." --repo ./path --partner client_a
         │
         ▼
Blueprint Engine (Python state machine)
    ├── DeterministicNode  →  fixed commands, guaranteed behavior
    └── AgenticNode        →  LLM loop, creative problem solving
         │
         ▼
Devbox Manager
    ├── Dev Containers (primary) — uses repo's .devcontainer/ if present
    └── Devbox.exec(command)     — abstraction, Blueprint never calls Docker directly
         │
         ▼
Agent Runtime (~50 lines)
    └── LiteLLM  →  unified API for Claude, Codex, Gemini via config
         │
         ▼
bash tool
    └── single tool: bash(command) → devbox.exec(command)
         └── agent uses shell natively — no hand-crafted tool wrappers
```

---

## Components

### 1. Blueprint Engine

A state machine that sequences nodes. Each Blueprint is a list of nodes with transitions.

**Node types:**

```python
@dataclass
class DeterministicNode:
    name: str
    command: str | None   # shell command to run in devbox; None = Python handler
    timeout: int          # seconds
    on_fail: Literal["abort", "warn", "escalate"]
    autofix: bool = False # apply --fix flags if available

@dataclass
class AgenticNode:
    name: str
    system_prompt: str    # task-specific instructions
    tools: list[Tool]     # subset of available tools
    max_tokens: int
    max_iterations: int   # hard cap on tool-calling rounds
    on_max_reached: Literal["abort", "escalate"]
```

**Context object** flows through all nodes:

```python
@dataclass
class BlueprintContext:
    task: str                    # original task description
    repo_path: str
    partner: str
    partner_config: PartnerConfig  # loaded from configs/partners/<partner>.yml
    devbox: Devbox
    conversation_history: list   # LiteLLM messages format
    artifacts: dict              # accumulated results: PR link, test output, etc.
    escalation_reason: str | None
```

**Standard Blueprint (V1):**

```python
STANDARD_BLUEPRINT = [
    DeterministicNode("boot_devbox",      command=None,            timeout=60,  on_fail="abort"),
    DeterministicNode("pre_flight_check", command=PREFLIGHT_CMDS,  timeout=30,  on_fail="abort"),
    DeterministicNode("qualify_task",     command=None,            timeout=10,  on_fail="escalate"),
    AgenticNode      ("plan",             system_prompt=PLAN_PROMPT,             max_iterations=10),
    AgenticNode      ("implement",        system_prompt=IMPL_PROMPT,             max_iterations=30),
    DeterministicNode("lint_autofix",     command="{lint} --fix",  timeout=60,  on_fail="warn",    autofix=True),
    DeterministicNode("run_tests",        command="{test}",        timeout=300, on_fail="continue"),
    AgenticNode      ("fix_failures",     system_prompt=FIX_PROMPT,             max_iterations=15, on_max_reached="escalate"),
    DeterministicNode("git_push",         command=GIT_PUSH_CMDS,   timeout=60,  on_fail="abort"),
    DeterministicNode("risk_classify_pr", command=None,            timeout=10,  on_fail="warn"),
    DeterministicNode("create_pr",        command=GH_PR_CMD,       timeout=30,  on_fail="abort"),
    DeterministicNode("report",           command=None,            timeout=5,   on_fail="warn"),
]
```

---

### 2. Devbox Manager

Manages the lifecycle of isolated development environments.

**Abstraction layer:**

```python
class Devbox(ABC):
    def start(self) -> None: ...
    def wait_until_ready(self) -> None: ...
    def exec(self, command: str, timeout: int = 60) -> ExecResult: ...
    def stop(self) -> None: ...

class DevContainerDevbox(Devbox):
    # Uses @devcontainers/cli
    # If repo has .devcontainer/ → use it directly
    # Else → use language-detected template

class DockerDevbox(Devbox):
    # Fallback for production EC2 / pre-warmed pools
```

**Environment layers (built on top of repo's devcontainer config):**

```
Layer 3 — Agent Tools (always injected)
    git, gh CLI, ripgrep, jq, bash 5+

Layer 2 — Linting + Testing (from partner config)
    Node:   eslint, prettier, jest
    Python: ruff, black, pytest
    Ruby:   rubocop, rspec

Layer 1 — Language Runtime (from .devcontainer/ or auto-detect)
    Runtime + package manager + dependencies installed
```

**Pre-flight checks (fail in <30 seconds):**

```bash
git remote -v                    # remote accessible?
gh auth status                   # gh CLI authenticated?
<package_manager> install        # dependencies install?
which <lint_tool>                # linter available?
<test_command> --list-tests 2>&1 # test runner runnable?
```

Any failure → immediate abort with structured error. Solves Stripe's 30-minute late-failure problem.

---

### 3. Agent Runtime

Manages the LLM tool-calling loop. ~50 lines. Sits above LiteLLM.

```python
def run_agent(
    system_prompt: str,
    tools: list[Tool],
    context: BlueprintContext,
    max_iterations: int,
) -> AgentResult:
    messages = context.conversation_history.copy()
    messages.append({"role": "user", "content": system_prompt})

    for _ in range(max_iterations):
        response = litellm.completion(
            model=context.partner_config.model,
            messages=messages,
            tools=tools,
        )

        if not response.tool_calls:
            return AgentResult(done=True, output=response.content)

        tool_results = []
        for call in response.tool_calls:
            result = execute_tool(call, context.devbox)
            tool_results.append(result)

        messages.append({"role": "assistant", "content": response.content, "tool_calls": response.tool_calls})
        messages.append({"role": "tool", "content": tool_results})

    return AgentResult(done=False, reason="max_iterations_reached")
```

**Provider switching via config:**

```yaml
# configs/partners/client_a.yml
llm_provider: claude
model: claude-sonnet-4-6
api_key_env: ANTHROPIC_API_KEY

# configs/partners/client_b.yml
llm_provider: openai
model: openai/o3
api_key_env: OPENAI_API_KEY
```

No code changes required. LiteLLM handles the translation.

---

### 4. Tools

**V1: single tool**

```python
@tool
def bash(command: str, context: BlueprintContext) -> str:
    """Execute a shell command in the devbox. Returns stdout + stderr."""
    result = context.devbox.exec(command, timeout=30)
    return result.stdout + result.stderr
```

Agent uses shell natively: reads files with `cat`, writes with `tee`, searches with `rg`, runs tests with the project's test command. No hand-crafted wrappers.

**V2 additions (when shell is insufficient):**
- `code_search(query)` — semantic search via Sourcegraph or ripgrep with context
- `read_ticket(id)` — fetch ticket details from Jira/Linear
- `load_docs(topic)` — pull internal documentation

---

### 5. Rule Files

**Format:** Cursor `.cursorrules` / Claude Code `.claude/` (same format, same files work for both).

**Loading strategy:**

```
repo/
├── .cursorrules                    # global repo rules
├── src/
│   ├── payments/
│   │   └── .cursorrules           # payments-specific rules
│   └── auth/
│       └── .cursorrules           # auth-specific rules
```

During `hydrate_context` (part of plan node), Blueprint:
1. Reads global `.cursorrules` at repo root
2. Traverses directories relevant to changed files
3. Loads scoped rules for those directories
4. Appends all to system prompt for subsequent agentic nodes

Not injected globally — only loaded for the directories the agent is actually touching. Avoids context saturation.

---

### 6. Task Qualification

Before the plan node, qualify incoming task:

```python
QUALIFICATION_CRITERIA = {
    "has_acceptance_criteria": 2,   # points
    "scope_is_estimable":      2,
    "no_known_blockers":       1,
    "reproducible_if_bug":     2,
    "not_requires_prod_data":  1,
}
MIN_SCORE = 5  # out of 8

def qualify_task(task: str) -> QualificationResult:
    score = score_task(task)
    if score < MIN_SCORE:
        return QualificationResult(
            qualified=False,
            missing=[...],
            escalation_message="Task needs more context before agent can proceed: ..."
        )
    return QualificationResult(qualified=True)
```

V1 scoring: keyword heuristics (checks for presence of "expected behavior", "steps to reproduce", file/function references, etc.). Not LLM-based in V1 — keeps qualification fast and deterministic. V2 can upgrade to LLM-assisted scoring.

Low-quality tickets → escalate to human immediately. Solves "bad input = bad output."

---

### 7. PR Risk Classification

After PR creation, classify review tier:

```
robot    — trivial, verified by CI only (lint fix, log update, dep bump)
1-brain  — one reviewer, standard change
2-brain  — two reviewers, architectural change or cross-cutting concern
3-brain  — full team, security / payment / compliance / framework change
```

Classification logic (V1: heuristic, V2: LLM-assisted):
- Lines changed > 200 → minimum 1-brain
- Files changed include auth/, payments/, security/ → minimum 3-brain
- Only test files changed → robot candidate
- New public API surface → minimum 2-brain

Applied as GitHub PR label. Human reviewer knows before opening the diff how much attention is needed.

---

### 8. Human Escalation

Triggered when:
- Pre-flight check fails
- Task qualification score too low
- Agent hits max iterations without resolution
- DeterministicNode fails with `on_fail: "escalate"`

Escalation report format:

```
ESCALATION REQUIRED
───────────────────
Task:     <original task description>
Stage:    fix_failures (iteration 2/2)
Reason:   Tests still failing after 2 attempts

What was tried:
  1. Fixed null pointer in auth.py line 42
  2. Attempted to mock the external dependency — mock not available in QA

Suggested next steps:
  - Check if QA environment has access to <service_name>
  - Consider adding fixture for this dependency

PR branch: minion/fix-auth-null-pointer-20260424
Last test output:
  <last 50 lines of test output>
```

CLI prints this. Slack integration in V2 sends to thread.

---

## Directory Structure

```
dev-box-minions/
├── CLAUDE.md                         # project context for Claude Code
├── minions/
│   ├── __init__.py
│   ├── cli.py                        # typer CLI entry point
│   ├── blueprint/
│   │   ├── engine.py                 # state machine runner
│   │   ├── nodes.py                  # DeterministicNode, AgenticNode
│   │   ├── context.py                # BlueprintContext dataclass
│   │   └── standard.py               # standard Blueprint definition
│   ├── devbox/
│   │   ├── base.py                   # Devbox abstract class
│   │   ├── devcontainer.py           # DevContainerDevbox
│   │   ├── docker.py                 # DockerDevbox (fallback)
│   │   ├── preflight.py              # pre-flight check logic
│   │   └── templates/                # language-specific devcontainer templates
│   │       ├── node.json
│   │       ├── python.json
│   │       └── ruby.json
│   ├── agent/
│   │   ├── runtime.py                # tool-calling loop (~50 lines)
│   │   └── tools.py                  # bash tool + V2 tools
│   ├── rules/
│   │   └── loader.py                 # rule file traversal + loading
│   └── qualify/
│       └── task.py                   # task qualification scoring
├── configs/
│   └── partners/
│       ├── default.yml
│       └── example_client.yml
├── blueprints/
│   └── standard.yml                  # V2: YAML Blueprint definitions
├── docs/
│   ├── stripe-minions-research-report.md
│   └── superpowers/specs/
│       └── 2026-04-24-minions-design.md
└── pyproject.toml
```

---

## Data Flow — Full Run

```
1.  Engineer: minion run --task "fix null check in auth" --repo ./client-a --partner client_a

2.  CLI: load configs/partners/client_a.yml
         initialize BlueprintContext

3.  boot_devbox [Det]:
        detect .devcontainer/ in repo → DevContainerDevbox
        inject agent layer (git, gh, rg, jq)
        devcontainer up → wait until ready

4.  pre_flight_check [Det]:
        devbox.exec("git remote -v")           → OK
        devbox.exec("gh auth status")           → OK
        devbox.exec("npm install")              → OK
        devbox.exec("which eslint")             → OK
        devbox.exec("npm test -- --listTests")  → OK

5.  qualify_task [Det]:
        score task description → 7/8 → qualified

6.  plan [Ag]:
        load rule files from .cursorrules (repo root + src/auth/)
        system_prompt = base + rules
        LiteLLM(claude-sonnet-4-6) + bash tool
        agent runs: cat src/auth.py, rg "null", understands scope
        outputs: plan with estimated 1-file change

7.  implement [Ag]:
        LiteLLM + bash tool
        agent: reads file, writes fix, verifies with cat

8.  lint_autofix [Det]:
        devbox.exec("eslint src/auth.js --fix") → clean

9.  run_tests [Det]:
        devbox.exec("npm test") → 2 failures

10. fix_failures [Ag]:
        LiteLLM + bash tool + test output in context
        agent fixes 2 failures
        devbox.exec("npm test") → all pass (checked inside node)

11. git_push [Det]:
        devbox.exec("git checkout -b minion/fix-null-auth-20260424")
        devbox.exec("git add -p")
        devbox.exec("git commit -m '...'")
        devbox.exec("git push origin HEAD")

12. risk_classify_pr [Det]:
        1 file changed, 8 lines, only src/auth.js
        → tier: 1-brain

13. create_pr [Det]:
        devbox.exec("gh pr create --title '...' --label '1-brain'")

14. report [Det]:
        ✓ PR created: https://github.com/client-a/repo/pull/482
        ✓ Risk tier: 1-brain (one reviewer needed)
        ✓ Duration: 4m 12s
        ✓ Tokens used: 24,830
```

---

## Error Handling

| Failure point | Behavior |
|---|---|
| boot_devbox fails | Abort, report environment error |
| pre_flight_check fails | Abort immediately, report which check failed |
| qualify_task score too low | Escalate to human, list what's missing |
| plan max_iterations | Escalate with what agent understood |
| implement max_iterations | Escalate with partial changes diff |
| lint fails (no autofix) | Warn, continue to tests |
| tests fail, fix_failures succeeds | Continue to push |
| tests fail, fix_failures max_iterations | Escalate with structured report |
| git_push fails | Abort, report git error |
| create_pr fails | Abort, branch is pushed, human can create PR manually |

---

## Testing Strategy

**Unit tests:** Blueprint state machine transitions, node execution, context passing, qualification scoring, risk classification heuristics.

**Integration tests:** Full Blueprint run against a real Git repo in a real Docker container. Use a test fixture repo with pre-seeded bugs. Verify PR is created, CI passes.

**No LLM mocking in integration tests:** Agent must run against real Claude API. Mocked LLM tests pass but don't catch prompt quality regressions — this is the exact failure mode that burned Stripe (mock/prod divergence).

**Evaluation metric (V1):**
- First-attempt success rate (PR passes CI without fix_failures node firing)
- Target: >50% on a curated set of 20 test tasks

---

## Configuration Schema

```yaml
# configs/partners/client_a.yml

partner: client_a
llm_provider: claude
model: claude-sonnet-4-6
api_key_env: ANTHROPIC_API_KEY

devbox:
  prefer_devcontainer: true          # use repo's .devcontainer/ if present
  language_fallback: node            # if no .devcontainer/ found

commands:
  lint: "eslint . --ext .js,.ts"
  test: "npm test"
  install: "npm install"

blueprint: standard                  # which Blueprint to use

tools:
  - bash                             # always included
  # - code_search                   # V2

rule_files:
  global: ".cursorrules"
  scoped: true                       # traverse subdirectory .cursorrules files

pr:
  base_branch: main
  risk_classification: true
  labels:
    robot: "minion:robot"
    1-brain: "minion:1-brain"
    2-brain: "minion:2-brain"
    3-brain: "minion:3-brain"
```

---

## Out of Scope (V1)

- Slack integration (Socket Mode bot)
- Multiple LLM providers (LiteLLM wired but only Claude tested)
- Task decomposition into multiple PRs
- Parallel devbox execution
- Observability dashboard
- YAML-based Blueprint authoring
- Semantic code search tool
- Ticket system integration
