"""
pytest + hypothesis configuration for edge device tests.

Registers a 'ci' hypothesis profile with max_examples=100 and
suppresses HealthCheck.too_slow for CI environments.
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
