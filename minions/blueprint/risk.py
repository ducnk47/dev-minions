from __future__ import annotations

_SENSITIVE_PATHS = ["auth", "security", "payment", "billing", "crypto", "secret", "token", "credential"]
_PUBLIC_API_SIGNALS = ["router", "endpoint", "controller", "views.py", "routes", "api/"]


def classify_pr_risk(files_changed: list[str], lines_changed: int) -> str:
    files_lower = [f.lower() for f in files_changed]

    # Pure test-only small changes are trivial regardless of file names
    all_test_files = all(
        "test" in f or "spec" in f or f.startswith("tests/")
        for f in files_lower
    )
    if all_test_files and lines_changed < 50:
        return "robot"

    if any(sensitive in f for f in files_lower for sensitive in _SENSITIVE_PATHS):
        return "3-brain"

    if lines_changed > 200:
        return "2-brain"
    if any(signal in f for f in files_lower for signal in _PUBLIC_API_SIGNALS):
        return "2-brain"

    return "1-brain"
