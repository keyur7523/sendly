import os
import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

_PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())
_PUBLIC_PEM = _PRIVATE_KEY.public_key().public_bytes(
    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
).decode()

APP_ID = "test-app-id"
TOKEN_ADDRESS = "0x1111111111111111111111111111111111111111"

# Settings are read at import time of app.main; configure the environment first.
os.environ.update(
    {
        "PRIVY_APP_ID": APP_ID,
        "PRIVY_VERIFICATION_KEY": _PUBLIC_PEM.replace("\n", "\\n"),
        "DEMO_TOKEN_ADDRESS": TOKEN_ADDRESS,
        "RPC_URL": "http://fake-rpc.invalid",
    }
)


def make_token(sub: str = "did:privy:alice") -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": sub, "iss": "privy.io", "aud": APP_ID, "iat": now, "exp": now + 3600},
        _PRIVATE_KEY,
        algorithm="ES256",
    )


@pytest.fixture
def auth_header():
    return lambda sub="did:privy:alice": {"Authorization": f"Bearer {make_token(sub)}"}
