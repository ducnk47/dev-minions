import pytest
from unittest.mock import MagicMock
from minions.devbox.base import ExecResult
from minions.devbox.preflight import run_preflight_checks, PreflightError
from minions.config import PartnerConfig


def _make_config(install="npm install", lint="eslint .", test="npm test"):
    return PartnerConfig(
        partner="test", llm_provider="claude", model="claude-sonnet-4-6",
        api_key_env="ANTHROPIC_API_KEY",
        devbox={"prefer_devcontainer": True, "language_fallback": "node"},
        commands={"lint": lint, "test": test, "install": install},
        blueprint="standard", tools=["bash"],
        rule_files={"global": ".cursorrules", "scoped": True},
        pr={"base_branch": "main", "risk_classification": True, "labels": {}},
    )


def _ok():
    return ExecResult(stdout="ok", stderr="", returncode=0)

def _fail(msg="error"):
    return ExecResult(stdout="", stderr=msg, returncode=1)


def test_all_checks_pass():
    devbox = MagicMock()
    devbox.exec.return_value = _ok()
    run_preflight_checks(devbox, _make_config())  # should not raise


def test_git_remote_fails():
    devbox = MagicMock()
    devbox.exec.side_effect = lambda cmd, **kw: _fail("not a git repo") if "git remote" in cmd else _ok()
    with pytest.raises(PreflightError, match="git remote"):
        run_preflight_checks(devbox, _make_config())


def test_gh_auth_fails():
    devbox = MagicMock()
    devbox.exec.side_effect = lambda cmd, **kw: _fail("not logged in") if "gh auth" in cmd else _ok()
    with pytest.raises(PreflightError, match="gh auth"):
        run_preflight_checks(devbox, _make_config())


def test_install_fails():
    devbox = MagicMock()
    devbox.exec.side_effect = lambda cmd, **kw: _fail("npm ERR!") if "npm install" in cmd else _ok()
    with pytest.raises(PreflightError, match="install"):
        run_preflight_checks(devbox, _make_config())
