"""
Tests for edge/estimator.py

Property 7: Distance Estimation is Positive and Monotonically Decreasing with Bbox Size
  Validates: Requirements 17.1

Property 8: Trajectory Vector Reflects Direction of Motion
  Validates: Requirements 17.2

Unit tests for estimate_distance and estimate_trajectory.
"""

import math
import pytest
from hypothesis import given, settings, HealthCheck, assume
from hypothesis import strategies as st

from edge.estimator import estimate_distance, estimate_trajectory


# ---------------------------------------------------------------------------
# Property 7: Distance estimation monotonicity
# Feature: anti-uav-detection-system, Property 7: Distance Estimation is Positive and Monotonically Decreasing with Bbox Size
# ---------------------------------------------------------------------------

@given(
    w1=st.floats(min_value=2.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    w2=st.floats(min_value=1.0, max_value=999.0, allow_nan=False, allow_infinity=False),
    frame_width=st.floats(min_value=100.0, max_value=4096.0, allow_nan=False, allow_infinity=False),
    fov=st.floats(min_value=10.0, max_value=170.0, allow_nan=False, allow_infinity=False),
    ref_size=st.floats(min_value=0.1, max_value=5.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property7_distance_monotonically_decreasing(w1, w2, frame_width, fov, ref_size):
    """
    Property 7: Distance Estimation is Positive and Monotonically Decreasing with Bbox Size
    If w1 > w2 > 0, then distance(w1) < distance(w2) and both are positive.
    """
    assume(w1 > w2 > 0)
    d1 = estimate_distance(w1, frame_width, fov, ref_size)
    d2 = estimate_distance(w2, frame_width, fov, ref_size)
    assert d1 > 0
    assert d2 > 0
    assert d1 < d2


# ---------------------------------------------------------------------------
# Property 8: Trajectory vector correctness
# Feature: anti-uav-detection-system, Property 8: Trajectory Vector Reflects Direction of Motion
# ---------------------------------------------------------------------------

@given(
    centroids=st.lists(
        st.tuples(
            st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
            st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
        ),
        min_size=2,
        max_size=20,
    ),
    window=st.integers(min_value=1, max_value=15),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property8_trajectory_equals_mean_displacement(centroids, window):
    """
    Property 8: Trajectory Vector Reflects Direction of Motion
    The computed (dx, dy) equals the mean of frame-to-frame displacements
    over the last window_frames frames.
    """
    result = estimate_trajectory(centroids, window)
    assert result is not None

    recent = centroids[-(window + 1):]
    displacements = [
        (recent[i + 1][0] - recent[i][0], recent[i + 1][1] - recent[i][1])
        for i in range(len(recent) - 1)
    ]
    expected_dx = sum(d[0] for d in displacements) / len(displacements)
    expected_dy = sum(d[1] for d in displacements) / len(displacements)

    assert result["dx"] == pytest.approx(expected_dx, rel=1e-6)
    assert result["dy"] == pytest.approx(expected_dy, rel=1e-6)


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

def test_distance_positive():
    d = estimate_distance(100, 640, 60, 0.5)
    assert d > 0


def test_distance_larger_bbox_closer():
    d_near = estimate_distance(200, 640, 60, 0.5)
    d_far = estimate_distance(50, 640, 60, 0.5)
    assert d_near < d_far


def test_distance_invalid_bbox_raises():
    with pytest.raises(ValueError):
        estimate_distance(0, 640, 60, 0.5)
    with pytest.raises(ValueError):
        estimate_distance(-10, 640, 60, 0.5)


def test_distance_invalid_fov_raises():
    with pytest.raises(ValueError):
        estimate_distance(100, 640, 0, 0.5)
    with pytest.raises(ValueError):
        estimate_distance(100, 640, 180, 0.5)


def test_trajectory_single_point_returns_none():
    assert estimate_trajectory([(0, 0)]) is None


def test_trajectory_empty_returns_none():
    assert estimate_trajectory([]) is None


def test_trajectory_two_points():
    result = estimate_trajectory([(0, 0), (3, 4)])
    assert result == pytest.approx({"dx": 3.0, "dy": 4.0})


def test_trajectory_constant_motion():
    # Moving right by 1 each frame
    centroids = [(float(i), 0.0) for i in range(10)]
    result = estimate_trajectory(centroids, window_frames=5)
    assert result["dx"] == pytest.approx(1.0)
    assert result["dy"] == pytest.approx(0.0)


def test_trajectory_window_limits_history():
    # 20 points, window=3 → uses last 4 points → 3 displacements
    centroids = [(float(i), 0.0) for i in range(20)]
    result = estimate_trajectory(centroids, window_frames=3)
    assert result is not None
    assert result["dx"] == pytest.approx(1.0)
