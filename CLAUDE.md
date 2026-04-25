# dev-box-minions — Project Context for Claude

## What This Project Is

A Stripe Minions-inspired autonomous coding agent system for an outsourcing company.
Engineers describe a task → agent writes code end-to-end → humans review the PR only.

Key constraint: **multi-repo, multi-partner** — each outsourcing client has a different codebase,
tech stack, and CI/CD pipeline. The system adapts per partner via config, not code changes.

Full spec: `docs/superpowers/specs/2026-04-24-minions-design.md`
Research report: `docs/stripe-minions-research-report.md`

---

## Architecture Decisions

### 1. Blueprint Engine (core orchestration)

Custom Python state machine with two node types:
- `DeterministicNode` — fixed shell commands, rigid and reliable (lint, git, test, push, PR)
- `AgenticNode` — LLM tool-calling loop, creative (plan, implement, fix failures)

`BlueprintContext` object flows through all nodes carrying task, devbox, conversation history, partner config, and artifacts.

**Standard V1 Blueprint flow:**
```
[Det] boot_devbox
[Det] pre_flight_check     ← fail fast < 30s, not 30 min like Stripe
[Det] qualify_task         ← reject bad tickets before spending tokens
[Ag]  plan
[Ag]  implement
[Det] lint_autofix
[Det] run_tests
[Ag]  fix_failures         ← max 1 retry, then escalate
[Det] git_push
[Det] risk_classify_pr     ← robot / 1-brain / 2-brain / 3-brain
[Det] create_pr
[Det] report
```

### 2. LiteLLM (provider abstraction)

**Do NOT use a custom `LLMProvider` abstract class.** We use **LiteLLM** instead.

LiteLLM is a unified API for 100+ LLM providers. Swap providers by changing the model string in config — zero code changes:

```python
# Same call, different model string per partner config
litellm.completion(model="claude-sonnet-4-6", messages=..., tools=...)
litellm.completion(model="openai/o3",         messages=..., tools=...)
litellm.completion(model="gemini/gemini-2.0-flash", messages=..., tools=...)
```

The agent runtime (~50 lines) sits above LiteLLM and manages the tool-calling while loop.

**Why not fork Goose:** Goose is its own agent harness — wrapping it inside our Blueprint creates nested complexity. LiteLLM + custom ~50-line runtime gives full Blueprint control with zero upstream maintenance burden.

### 3. Devbox (sandboxed environment)

**Dev Containers** (not vanilla Docker). Uses `@devcontainers/cli`.

- If the partner's repo already has `.devcontainer/devcontainer.json` → use it directly
- Otherwise → auto-detect language and apply a template from `minions/devbox/templates/`
- Always inject agent layer on top: `git`, `gh CLI`, `ripgrep`, `jq`

Access is abstracted behind `Devbox.exec(command)` — Blueprint nodes never call Docker or devcontainer CLI directly. Swap implementation (DevContainerDevbox vs DockerDevbox) via config without touching Blueprint.

### 4. Primary Tool: bash

The agent has **one tool: `bash(command)`**, which calls `devbox.exec(command)`.

Do NOT define individual tools like `read_file`, `write_file`, `run_lint`, `run_tests`. The agent already knows shell. It uses `cat`, `tee`, `rg`, `git`, `npm test` natively.

```python
@tool
def bash(command: str, context: BlueprintContext) -> str:
    result = context.devbox.exec(command, timeout=30)
    return result.stdout + result.stderr
```

V2 will add `code_search`, `read_ticket`, `load_docs` when bash proves insufficient.

### 5. Rule Files

Cursor `.cursorrules` / Claude Code `.claude/` format (same files work for both).

- Loaded lazily during the `plan` agentic node — only for directories the agent is actually touching
- Global `.cursorrules` at repo root always loaded
- Directory-scoped `.cursorrules` appended per subdirectory traversed
- Never loaded globally — avoids context saturation

### 6. Feedback Loop

- `lint_autofix` deterministic node: run linter with `--fix`, no LLM involved
- `run_tests` deterministic node: run test suite, capture output
- `fix_failures` agentic node: LLM attempts fix once with test output in context
- Hard cap: max 1 `fix_failures` retry → escalate after that
- No indefinite spinning (Stripe lesson: diminishing returns after 2 rounds)

### 7. Task Qualification

Before the agent starts coding, `qualify_task` scores the incoming task using keyword heuristics (V1):

- Has acceptance criteria? Has steps to reproduce? Scope estimable? No prod data required?
- Score < 5/8 → immediate escalation with list of what's missing
- Rejects badly-written tickets before wasting any tokens

### 8. PR Risk Classification

After `git_push`, classify the PR tier before creating it:

| Tier | Meaning |
|---|---|
| `robot` | trivial — lint fix, log update, dep bump |
| `1-brain` | standard change, one reviewer |
| `2-brain` | architectural or cross-cutting, two reviewers |
| `3-brain` | security / compliance / framework, full team |

V1: heuristic (lines changed, files touched, path patterns like `auth/`, `security/`).
Applied as GitHub PR label so reviewers know review depth before opening the diff.

### 9. Human Escalation

Triggered when: pre-flight fails, task score too low, agent hits max iterations, or a deterministic node fails with `on_fail="escalate"`.

Escalation prints a structured report to CLI: stage, reason, what was tried, suggested next steps, branch name, last 50 lines of test output.

---

## Per-Partner Config

```yaml
# configs/partners/client_a.yml

partner: client_a
llm_provider: claude
model: claude-sonnet-4-6
api_key_env: ANTHROPIC_API_KEY

devbox:
  prefer_devcontainer: true
  language_fallback: node

commands:
  lint: "eslint . --ext .js,.ts"
  test: "npm test"
  install: "npm install"

blueprint: standard

tools:
  - bash

rule_files:
  global: ".cursorrules"
  scoped: true

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

## Key Design Principles

1. Strict engineering workflow — no shortcuts
2. Sandboxed environment — isolated per run, no prod access
3. Determinism + nondeterminism — deterministic nodes are rigid; LLM nodes are creative
4. Guardrails at every node — timeout, max iterations, on_fail behavior
5. Fail fast — pre-flight checks catch environment issues in < 30s
6. Human escalation — structured report, never spin indefinitely
7. No manual code writing — all manual final review only

---

## Tech Stack

- Language: Python 3.12
- LLM: LiteLLM (unified API — Claude, Codex, Gemini via config string)
- Agent runtime: custom ~50-line tool-calling loop above LiteLLM
- Devbox: Dev Containers (`@devcontainers/cli`) → Docker under the hood
- Primary tool: `bash` → `devbox.exec()`
- CLI: `typer`
- Config: `pyyaml`
- Tests: `pytest`
- Entry point: CLI (V1), Slack Socket Mode (V2)

---

## Out of Scope (V1)

- Slack integration
- Multiple LLM providers (LiteLLM wired, Claude only tested)
- Task decomposition into multiple PRs
- Parallel devbox execution
- Observability dashboard
- Semantic code search tool
- Ticket system integration
