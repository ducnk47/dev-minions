import pytest
from src.math import divide

def test_divide_normal():
    assert divide(10, 2) == 5.0

def test_divide_by_zero():
    with pytest.raises(ZeroDivisionError):
        divide(1, 0)  # this test exists but divide() will raise unhandled — that's the bug to fix
