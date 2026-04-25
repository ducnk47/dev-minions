# dev-box-minions

An autonomous coding agent that takes a task description, writes code changes inside an isolated Docker container, and opens a labeled GitHub PR — no human involvement during execution.

Inspired by [Stripe Minions](https://stripe.com/blog/minions-autonomous-coding).

---

## How it works

```
You describe a task
       ↓
Agent boots an isolated Docker container for the target repo
       ↓
Pre-flight checks (git remote, gh auth, dependencies — fails fast in < 30s)
       ↓
LLM plans the changes, then implements them using bash inside the container
       ↓
Linter runs automatically, tests run, failures get one fix attempt
       ↓
PR is opened with a risk label: robot / 1-brain / 2-brain / 3-brain
       ↓
You review and merge
```

---

## Prerequisites

You need the following installed on your machine:

| Tool | Install |
|---|---|
| Python 3.9+ | Already installed on macOS |
| Node.js 18+ | `brew install node` |
| Docker Desktop | [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/) |
| Dev Containers CLI | `npm install -g @devcontainers/cli` |
| GitHub CLI | `brew install gh` |

Verify everything is installed:

```bash
python3 --version      # 3.9+
node --version         # 18+
docker --version       # any recent version
devcontainer --version # any
gh --version           # any
```

---

## Setup

**1. Clone this repo**

```bash
git clone <this-repo-url>
cd dev-box-minions
```

**2. Create a virtual environment and install dependencies**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

This installs the `minion` CLI command and all dependencies inside an isolated environment.

> **Every time you open a new terminal**, you need to activate the virtual environment first:
> ```bash
> cd dev-box-minions
> source .venv/bin/activate
> ```
> You'll know it's active when you see `(.venv)` at the start of your prompt.

**3. Set your Anthropic API key**

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Add this to your `~/.zshrc` or `~/.bashrc` to make it permanent.

**4. Authenticate GitHub CLI**

```bash
gh auth login
```

Follow the prompts. Choose GitHub.com → HTTPS → authenticate with browser.

**5. Start Docker Desktop**

Make sure Docker Desktop is running before you use the tool.

---

## Running a minion

Basic usage:

```bash
minion --task "your task description" --repo /path/to/target/repo
```

Example:

```bash
minion \
  --task "Fix the null pointer exception in src/auth/service.py line 42. Expected: login returns 401 on missing password. Steps to reproduce: POST /login with empty body." \
  --repo /path/to/client-app
```

The agent will:
1. Boot a Dev Container for the repo (uses `.devcontainer/` if it exists, otherwise auto-detects the language)
2. Check pre-flight conditions (git remote reachable, gh authenticated, deps installed)
3. Score the task quality — if the task is too vague, it will stop and tell you what's missing
4. Plan and implement the changes
5. Run lint and tests, attempt one auto-fix if tests fail
6. Push a branch and open a PR labeled with a review depth tier

---

## Writing good tasks

The agent rejects vague tasks before spending any tokens. A good task has:

- **What file / function is affected** — `src/auth/service.py`, `UserController.login()`
- **Expected behavior** — what should happen when it works
- **Steps to reproduce** (for bugs) — exact request, command, or input
- **No production data required** — the agent runs in a sandbox

**Good task:**
```
Fix the null pointer exception in src/auth/service.py line 42.
Expected behavior: login should return 401, not crash.
Steps to reproduce: POST /login with missing password field.
```

**Bad task (will be rejected):**
```
fix the bug
```

---

## Partner configs

The tool adapts to each client repo via a YAML config in `configs/partners/`.

**Default config** (`configs/partners/default.yml`) — Node.js/TypeScript:
```yaml
partner: default
model: claude-sonnet-4-6
commands:
  lint: "eslint . --ext .js,.ts"
  test: "npm test"
  install: "npm install"
```

**Example Python config** (`configs/partners/example_client.yml`):
```yaml
partner: example_client
model: claude-sonnet-4-6
commands:
  lint: "ruff check . --fix"
  test: "pytest"
  install: "pip install -e ."
```

**To use a specific partner config:**

```bash
minion --task "..." --repo /path/to/repo --partner example_client
```

**To add a new partner**, copy an existing config file and adjust the commands:

```bash
cp configs/partners/default.yml configs/partners/my_client.yml
# Edit my_client.yml with the correct lint/test/install commands
minion --task "..." --repo /path/to/repo --partner my_client
```

---

## PR risk tiers

Every PR opened by the agent gets a GitHub label indicating how much review it needs:

| Label | Meaning | Examples |
|---|---|---|
| `minion:robot` | Trivial, can auto-merge | lint fix, dep bump, log update |
| `minion:1-brain` | One reviewer | standard feature or bug fix |
| `minion:2-brain` | Two reviewers | large change or public API surface |
| `minion:3-brain` | Full team review | auth, security, billing, payments |

---

## Running tests

Unit tests (no Docker required):

```bash
python3 -m pytest tests/unit/ -v
```

Integration tests (requires Docker + `ANTHROPIC_API_KEY`):

```bash
MINION_INTEGRATION=1 python3 -m pytest tests/integration/ -v
```

The integration test runs the agent on a small fixture repo with a deliberate bug in a `divide()` function and verifies the agent fixes it.

---

## Troubleshooting

**"externally-managed-environment" error when running pip**
Your system Python is protected. Use a virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

**"command not found: minion" after install**
The virtual environment is not active. Run `source .venv/bin/activate` first.

**"Partner config not found"**
Make sure the partner name matches a file in `configs/partners/`. Example: `--partner example_client` looks for `configs/partners/example_client.yml`.

**"Pre-flight check failed: gh CLI not authenticated"**
Run `gh auth login` and complete the authentication flow.

**"Pre-flight check failed: git remote not accessible"**
The target repo must have a git remote configured (`git remote -v` should show a URL).

**"Task qualification failed"**
The task description is too vague. Read the message — it will list exactly what's missing (acceptance criteria, reproduction steps, code location).

**"Docker is not running"**
Start Docker Desktop, or on Linux: `sudo systemctl start docker`. Then retry.

**"devcontainer CLI not found"**
Install it: `npm install -g @devcontainers/cli`

**"devcontainer up failed" with no clear message**
Run this manually to see the full error:
```bash
devcontainer up --workspace-folder /path/to/your/repo
```
Common causes: Docker daemon not started, insufficient disk space, or network issues pulling the image.

**Slow first run**
The first run downloads the Dev Container base image (can take 2–5 minutes depending on connection). Subsequent runs use Docker's cache and are much faster.

**Agent hits max iterations and escalates**
The agent tried but could not complete the task within the iteration limit. The escalation output shows the stage where it stopped, what was tried, and the last test output. Usually this means the task is too large — break it into smaller pieces.

---

## Project structure

```
dev-box-minions/
├── minions/
│   ├── cli.py              # Entry point: minion --task ... --repo ...
│   ├── config.py           # PartnerConfig — per-client YAML settings
│   ├── blueprint/          # State machine orchestration
│   │   ├── engine.py       # BlueprintEngine runner
│   │   ├── nodes.py        # DeterministicNode, AgenticNode
│   │   ├── standard.py     # The 13-node V1 blueprint
│   │   ├── prompts.py      # LLM system prompts
│   │   └── risk.py         # PR risk classification
│   ├── devbox/             # Docker / Dev Containers sandbox
│   │   ├── devcontainer.py # Main implementation
│   │   ├── preflight.py    # Pre-flight checks
│   │   └── templates/      # Fallback devcontainer configs (node, python, ruby)
│   ├── agent/              # LLM tool-calling loop
│   │   ├── runtime.py      # run_agent() — LiteLLM loop
│   │   └── tools.py        # bash tool definition
│   ├── rules/loader.py     # Reads .cursorrules / CLAUDE.md / AGENTS.md
│   ├── skills/loader.py    # Loads SuperPowers skill files
│   └── qualify/task.py     # Task quality scoring
├── configs/partners/       # Per-client YAML configs
└── tests/
    ├── unit/               # 43 unit tests, no Docker needed
    └── integration/        # Full end-to-end test (requires Docker)
```
