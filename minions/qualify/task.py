from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class QualificationResult:
    qualified: bool
    missing: list[str] = field(default_factory=list)
    escalation_message: str = ""


_CRITERIA = {
    "has_acceptance_criteria": (
        2,
        ["expected behavior", "expected result", "acceptance criteria", "should return", "should work"],
    ),
    "has_reproduction_steps": (
        2,
        ["steps to reproduce", "to reproduce", "repro:", "how to reproduce", "curl ", "post /", "get /"],
    ),
    "references_code_location": (
        2,
        [".py", ".js", ".ts", ".rb", "line ", "function ", "method ", "class ", "src/", "lib/"],
    ),
    "scope_is_bounded": (
        1,
        ["only", "just", "specifically", "the ", "in file", "this function", "this method"],
    ),
    "no_prod_data_required": (
        1,
        [],  # negative check
    ),
}

MIN_SCORE = 4


def qualify_task(task: str) -> QualificationResult:
    task_lower = task.lower()
    score = 0
    missing = []

    points, keywords = _CRITERIA["has_acceptance_criteria"]
    if any(kw in task_lower for kw in keywords):
        score += points
    else:
        missing.append("acceptance criteria (what does 'done' look like?)")

    points, keywords = _CRITERIA["has_reproduction_steps"]
    if any(kw in task_lower for kw in keywords):
        score += points
    else:
        missing.append("reproduction steps or request example")

    points, keywords = _CRITERIA["references_code_location"]
    if any(kw in task_lower for kw in keywords):
        score += points
    else:
        missing.append("file path, function name, or code location")

    points, keywords = _CRITERIA["scope_is_bounded"]
    if any(kw in task_lower for kw in keywords):
        score += points

    if any(kw in task_lower for kw in ["production data", "prod db", "live data", "real users"]):
        score -= 2
        missing.append("task requires production data (not available in devbox)")

    qualified = score >= MIN_SCORE and not any("production data" in m for m in missing)

    escalation_message = ""
    if not qualified:
        items = "\n  - ".join(missing)
        escalation_message = (
            f"Task qualification failed (score {score}/{MIN_SCORE} required).\n"
            f"Missing:\n  - {items}\n\n"
            f"Please add this information to the task and re-submit."
        )

    return QualificationResult(qualified=qualified, missing=missing, escalation_message=escalation_message)
