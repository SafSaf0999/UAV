"""
pytest + hypothesis configuration for aggregation service tests.
"""

from hypothesis import HealthCheck, settings

settings.register_profile(
    "ci",
    max_examples=100,
    suppress_health_check=[HealthCheck.too_slow],
)

settings.register_profile(
    "dev",
    max_examples=20,
    suppress_health_check=[HealthCheck.too_slow],
)

settings.load_profile("ci")
