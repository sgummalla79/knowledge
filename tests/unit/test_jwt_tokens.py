import jwt
import pytest

from app import create_app
from app.infrastructure.auth.jwt_tokens import decode_access_token, issue_access_token


@pytest.fixture()
def app_context():
    app = create_app(testing=True)
    with app.app_context():
        yield app


def test_issue_then_decode_round_trip(app_context):
    token = issue_access_token("app-id-123", ["libraries:read", "query:execute"], ttl_seconds=60)
    claims = decode_access_token(token)
    assert claims is not None
    assert claims["sub"] == "app-id-123"
    assert claims["scope"] == "libraries:read query:execute"


def test_expired_token_decodes_to_none(app_context):
    token = issue_access_token("app-id-123", ["libraries:read"], ttl_seconds=-10)
    assert decode_access_token(token) is None


def test_tampered_token_decodes_to_none(app_context):
    token = issue_access_token("app-id-123", ["libraries:read"], ttl_seconds=60)
    tampered = token[:-2] + ("aa" if token[-2:] != "aa" else "bb")
    assert decode_access_token(tampered) is None


def test_token_signed_with_wrong_key_decodes_to_none(app_context):
    bogus = jwt.encode({"sub": "x", "scope": "", "exp": 9999999999}, "wrong-key", algorithm="HS256")
    assert decode_access_token(bogus) is None
