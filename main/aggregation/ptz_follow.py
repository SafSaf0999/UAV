"""
Aggregation service — PTZ follow bearing computation.

Computes the absolute compass bearing a follower camera should pan to
in order to track a detected object seen by a leader camera.

Requirements: 7.2, 7.4
"""


def compute_bearing(cx: float, compass_bearing: float, fov_deg: float = 60.0) -> float:
    """
    Compute the absolute compass bearing for PTZ follow.

    Args:
        cx:               Normalized horizontal bounding-box center in [0, 1].
                          0.0 = left edge, 0.5 = center, 1.0 = right edge.
        compass_bearing:  Current compass heading of the leader camera (degrees).
        fov_deg:          Horizontal field of view of the leader camera (degrees).
                          Defaults to 60.0.

    Returns:
        Absolute bearing in [0, 360) degrees.

    Formula:
        bearing = (compass_bearing + (cx - 0.5) * fov_deg) % 360
    """
    bearing = (compass_bearing + (cx - 0.5) * fov_deg) % 360.0
    # Ensure result is in [0, 360) — Python % already guarantees this for positive modulus
    if bearing < 0.0:
        bearing += 360.0
    return bearing
