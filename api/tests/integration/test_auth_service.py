import pytest

from api.application.auth_service import AuthService
from api.domain import error_codes
from api.domain.errors import AuthenticationError, ConflictError, ValidationError
from api.infrastructure.auth.password_identity_verifier import PasswordIdentityVerifier
from api.infrastructure.auth.passwords import hash_password
from api.infrastructure.repositories.identity_repository import IdentityRepository
from api.infrastructure.repositories.org_member_repository import OrgMemberRepository


def _auth_service(db_session) -> AuthService:
    identities = IdentityRepository(db_session)
    return AuthService(identities, PasswordIdentityVerifier(identities), OrgMemberRepository(db_session))


def _identity(db_session, username="ada@acme.com", password="a-strong-password"):
    identity = IdentityRepository(db_session).create(username, hash_password(password), name="Ada")
    db_session.commit()
    return identity


def test_update_profile_changes_name_and_email(db_session):
    identity = _identity(db_session)

    updated = _auth_service(db_session).update_profile(identity.id, "Ada Lovelace", "ada-contact@acme.com")
    db_session.commit()

    assert updated.name == "Ada Lovelace"
    assert updated.email == "ada-contact@acme.com"
    assert updated.username == identity.username


def test_update_profile_rejects_malformed_email(db_session):
    identity = _identity(db_session)

    with pytest.raises(ValidationError):
        _auth_service(db_session).update_profile(identity.id, "Ada", "not-an-email")


def test_change_username_succeeds_with_correct_password(db_session):
    identity = _identity(db_session, password="correct-password")

    updated = _auth_service(db_session).change_username(identity.id, "correct-password", "new-username@acme.com")
    db_session.commit()

    assert updated.username == "new-username@acme.com"
    assert IdentityRepository(db_session).get_by_username("new-username@acme.com") is not None


def test_change_username_rejects_wrong_password(db_session):
    """Regression test: a wrong re-verification password must carry the distinct
    INCORRECT_PASSWORD code, not the generic UNAUTHORIZED one -- the frontend client
    (webui/src/api/client.ts) uses this to avoid forcing a sign-out/redirect on a simple
    wrong-password retry, which UNAUTHORIZED would otherwise trigger for any 401."""
    identity = _identity(db_session, password="correct-password")

    with pytest.raises(AuthenticationError) as exc_info:
        _auth_service(db_session).change_username(identity.id, "wrong-password", "new-username@acme.com")
    db_session.commit()

    assert exc_info.value.code == error_codes.INCORRECT_PASSWORD
    assert identity.username == IdentityRepository(db_session).get_by_id(identity.id).username


def test_change_username_rejects_malformed_new_username(db_session):
    identity = _identity(db_session, password="correct-password")

    with pytest.raises(ValidationError):
        _auth_service(db_session).change_username(identity.id, "correct-password", "not-an-email")


def test_change_username_rejects_taken_username(db_session):
    _identity(db_session, username="existing@acme.com", password="pw")
    identity = _identity(db_session, username="ada@acme.com", password="correct-password")

    with pytest.raises(ConflictError):
        _auth_service(db_session).change_username(identity.id, "correct-password", "existing@acme.com")
