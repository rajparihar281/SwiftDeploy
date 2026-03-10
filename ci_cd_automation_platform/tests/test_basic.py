def test_example():
    assert 1 == 1

import math


def test_basic_math():
    """Simple math test"""
    assert 2 + 2 == 4


def test_string_operations():
    """Check string manipulation"""
    text = "ci_cd_pipeline"
    assert text.upper() == "CI_CD_PIPELINE"


def test_list_operations():
    """Check list operations"""
    data = [1, 2, 3, 4]
    assert len(data) == 4
    assert sum(data) == 10


def test_dictionary_access():
    """Check dictionary behavior"""
    user = {"name": "Batman", "role": "DevOps"}
    assert user["name"] == "Batman"


def test_math_functions():
    """Check Python math functions"""
    assert math.sqrt(16) == 4


def test_boolean_logic():
    """Check boolean logic"""
    assert (5 > 3) is True


def test_sorting():
    """Check sorting works"""
    arr = [5, 2, 3, 1]
    arr.sort()
    assert arr == [1, 2, 3, 5]