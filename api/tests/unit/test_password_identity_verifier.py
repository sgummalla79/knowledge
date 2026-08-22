from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from api.domain.entities import Identity
from api.infrastructure.auth.passwords import hash_password
from api.infrastructure.auth.password_identity_verifier import PasswordIdentityVerifier

# Security-review regression (see this repo's Phase A history): verify() must not short-circuit
# on a missing identity without still doing real password-hash work — an early return there is a
# timing side-channel an attacker could use to enumerate valid usernames, since the slow hash
# comparison would only ever run for a username that actually exists.


class _FakeIdentities:
    def __init__(self, identity=None):
        self._identity = identity

    def get_by_username(self, username):
        return self._identity if self._identity is not None and self._identity.username == username else None


def _identity(**overrides):
    fields = dict(
        id=uuid4(),
        username="admin@local",
        email=None,
        name="Admin",
        password_hash=hash_password("correct-password"),
        must_change_password=False,
        created_at=datetime.now(timezone.utc),
        last_modified_at=datetime.now(timezone.utc),
        last_active_at=None,
    )
    fields.update(overrides)
    return Identity(**fields)


def test_verify_calls_password_hash_comparison_even_when_identity_does_not_exist():
    verifier = PasswordIdentityVerifier(_FakeIdentities(identity=None))

    with patch(
        "api.infrastructure.auth.password_identity_verifier.verify_password", return_value=False
    ) as mock_verify:
        result = verifier.verify("nobody@example.com", "whatever")

    assert result is None
    mock_verify.assert_called_once()


def test_verify_returns_none_for_wrong_password():
    identity = _identity()
    verifier = PasswordIdentityVerifier(_FakeIdentities(identity))

    assert verifier.verify("admin@local", "wrong-password") is None


def test_verify_returns_identity_for_correct_password():
    identity = _identity()
    verifier = PasswordIdentityVerifier(_FakeIdentities(identity))

    assert verifier.verify("admin@local", "correct-password") == identity


def test_verify_returns_none_for_unknown_username():
    verifier = PasswordIdentityVerifier(_FakeIdentities(identity=None))

    assert verifier.verify("nobody@example.com", "anything") is None
