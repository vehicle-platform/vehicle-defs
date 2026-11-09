"""ISSUES C-9 (1): a non-finite table limit never reaches gen/."""

import math

import pytest

from vehicle_codegen.gen_c import _c_float


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_non_finite_limit_is_refused(value):
    with pytest.raises(ValueError, match="non-finite"):
        _c_float(value)


def test_finite_limit_is_emitted():
    assert _c_float(2.5) == "2.5f"
    assert _c_float(-90) == "-90.0f"
