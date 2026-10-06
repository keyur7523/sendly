import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.auth.privy import InvalidToken, verify_access_token

APP_ID = "test-app-id"


@pytest.fixture(scope="module")
def keys():
    private = ec.generate_private_key(ec.SECP256R1())
    public_pem = private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    return private, public_pem


def token(private, **overrides):
    now = int(time.time())
    claims = {"sub": "did:privy:abc", "sid": "s1", "iss": "privy.io", "aud": APP_ID, "iat": now, "exp": now + 3600}
    claims.update(overrides)
    return jwt.encode({k: v for k, v in claims.items() if v is not None}, private, algorithm="ES256")


def test_valid_token(keys):
    private, public = keys
    user = verify_access_token(token(private), app_id=APP_ID, verification_key=public)
    assert user.privy_did == "did:privy:abc"


@pytest.mark.parametrize(
    "overrides",
    [{"aud": "other-app"}, {"iss": "evil.io"}, {"exp": int(time.time()) - 10}, {"sub": None}],
)
def test_rejected_claims(keys, overrides):
    private, public = keys
    with pytest.raises(InvalidToken):
        verify_access_token(token(private, **overrides), app_id=APP_ID, verification_key=public)


def test_rejects_other_signing_key(keys):
    _, public = keys
    other = ec.generate_private_key(ec.SECP256R1())
    with pytest.raises(InvalidToken):
        verify_access_token(token(other), app_id=APP_ID, verification_key=public)


def test_rejects_algorithm_confusion(keys):
    """An HS256 token 'signed' with the public key must not verify."""
    _, public = keys
    forged = jwt.encode(
        {"sub": "did:privy:attacker", "iss": "privy.io", "aud": APP_ID, "iat": 0, "exp": int(time.time()) + 60},
        "not-the-key",
        algorithm="HS256",
    )
    with pytest.raises(InvalidToken):
        verify_access_token(forged, app_id=APP_ID, verification_key=public)
