"""
Property test: Webhook HMAC signature is verifiable.

Feature: uav-control-center-v3
Property 10: Webhook HMAC signature is verifiable
Validates: Requirements 8.6
"""

import hashlib
import hmac

from hypothesis import given, settings
from hypothesis import strategies as st

from main.aggregation.webhook_dispatcher import _compute_signature


@given(
    body=st.binary(min_size=0, max_size=4096),
    secret=st.text(min_size=1, max_size=256),
)
@settings(max_examples=500)
def test_hmac_signature_verifiable(body: bytes, secret: str):
    """Property 10: X-UAV-Signature can be independently verified by the receiver."""
    signature = _compute_signature(body, secret)

    # Must start with the expected prefix
    assert signature.startswith("hmac-sha256="), (
        f"Signature missing prefix: {signature!r}"
    )

    # Extract hex digest
    hex_digest = signature[len("hmac-sha256="):]

    # Independently compute expected HMAC
    expected = hmac.new(
        secret.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()

    assert hex_digest == expected, (
        f"HMAC mismatch: got {hex_digest!r}, expected {expected!r}"
    )


@given(
    body=st.binary(min_size=1, max_size=1024),
    secret=st.text(min_size=1, max_size=64),
    wrong_secret=st.text(min_size=1, max_size=64),
)
@settings(max_examples=200)
def test_hmac_different_secrets_differ(body: bytes, secret: str, wrong_secret: str):
    """Different secrets produce different signatures (with overwhelming probability)."""
    if secret == wrong_secret:
        return  # skip equal secrets
    sig1 = _compute_signature(body, secret)
    sig2 = _compute_signature(body, wrong_secret)
    assert sig1 != sig2, "Different secrets produced identical HMAC signatures"
