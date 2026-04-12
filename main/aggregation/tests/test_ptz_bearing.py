"""
Property test: PTZ bearing is always in [0, 360).

Feature: uav-control-center-v3
Property 9: PTZ bearing is always in [0, 360)
Validates: Requirements 7.2, 7.4
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from main.aggregation.ptz_follow import compute_bearing


@given(
    cx=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    compass_bearing=st.floats(min_value=0.0, max_value=360.0, allow_nan=False, allow_infinity=False),
    fov_deg=st.floats(min_value=1.0, max_value=180.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=500)
def test_bearing_always_in_range(cx, compass_bearing, fov_deg):
    """Property 9: compute_bearing always returns a value in [0, 360)."""
    result = compute_bearing(cx, compass_bearing, fov_deg)
    assert 0.0 <= result < 360.0, (
        f"bearing={result} out of range for cx={cx}, "
        f"compass={compass_bearing}, fov={fov_deg}"
    )


@given(
    cx=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    compass_bearing=st.floats(min_value=0.0, max_value=360.0, allow_nan=False, allow_infinity=False),
)
def test_bearing_center_equals_compass(cx, compass_bearing):
    """When cx=0.5 (center), bearing equals compass_bearing (mod 360)."""
    result = compute_bearing(0.5, compass_bearing)
    expected = compass_bearing % 360.0
    assert abs(result - expected) < 1e-9 or abs(result - expected - 360.0) < 1e-9
