import pytest
from minions.devbox.base import Devbox, ExecResult


def test_exec_result_success():
    r = ExecResult(stdout="hello\n", stderr="", returncode=0)
    assert r.ok is True


def test_exec_result_failure():
    r = ExecResult(stdout="", stderr="error", returncode=1)
    assert r.ok is False


def test_devbox_is_abstract():
    with pytest.raises(TypeError):
        Devbox()
