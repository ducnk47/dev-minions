import pytest
from pathlib import Path
from minions.devbox.base import Devbox, ExecResult
from minions.devbox.devcontainer import _detect_language


def test_exec_result_success():
    r = ExecResult(stdout="hello\n", stderr="", returncode=0)
    assert r.ok is True


def test_exec_result_failure():
    r = ExecResult(stdout="", stderr="error", returncode=1)
    assert r.ok is False


def test_devbox_is_abstract():
    with pytest.raises(TypeError):
        Devbox()


def test_detect_language_python(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'")
    assert _detect_language(tmp_path) == "python"


def test_detect_language_python_requirements(tmp_path):
    (tmp_path / "requirements.txt").write_text("flask")
    assert _detect_language(tmp_path) == "python"


def test_detect_language_node(tmp_path):
    (tmp_path / "package.json").write_text("{}")
    assert _detect_language(tmp_path) == "node"


def test_detect_language_ruby(tmp_path):
    (tmp_path / "Gemfile").write_text("source 'https://rubygems.org'")
    assert _detect_language(tmp_path) == "ruby"


def test_detect_language_unknown_returns_none(tmp_path):
    assert _detect_language(tmp_path) is None


def test_detect_language_python_beats_node(tmp_path):
    # pyproject.toml + package.json in same repo → python wins (listed first)
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'")
    (tmp_path / "package.json").write_text("{}")
    assert _detect_language(tmp_path) == "python"
