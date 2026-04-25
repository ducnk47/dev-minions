from minions.qualify.task import qualify_task, QualificationResult


def test_well_formed_task_qualifies():
    task = (
        "Fix the null pointer exception in src/auth/service.py line 42. "
        "Expected behavior: login should return 401, not crash. "
        "Steps to reproduce: POST /login with missing password field."
    )
    result = qualify_task(task)
    assert result.qualified is True


def test_vague_task_does_not_qualify():
    result = qualify_task("fix the bug")
    assert result.qualified is False
    assert len(result.missing) > 0


def test_escalation_message_lists_missing():
    result = qualify_task("do something")
    assert result.escalation_message != ""
    assert "missing" in result.escalation_message.lower() or len(result.missing) > 0
