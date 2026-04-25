from minions.blueprint.risk import classify_pr_risk


def test_robot_tier_for_small_test_only_change():
    tier = classify_pr_risk(files_changed=["tests/test_auth.py"], lines_changed=15)
    assert tier == "robot"


def test_one_brain_for_standard_change():
    tier = classify_pr_risk(files_changed=["src/utils.py"], lines_changed=30)
    assert tier == "1-brain"


def test_three_brain_for_auth_file():
    tier = classify_pr_risk(files_changed=["src/auth/service.py"], lines_changed=20)
    assert tier == "3-brain"


def test_two_brain_for_large_change():
    files = [f"src/module_{i}.py" for i in range(5)]
    tier = classify_pr_risk(files_changed=files, lines_changed=250)
    assert tier == "2-brain"
