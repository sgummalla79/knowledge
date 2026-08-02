from app.infrastructure.auth.pkce import compute_code_challenge, verify_pkce


def test_verify_pkce_accepts_matching_verifier():
    verifier = "a" * 64
    challenge = compute_code_challenge(verifier)
    assert verify_pkce(verifier, challenge, "S256") is True


def test_verify_pkce_rejects_wrong_verifier():
    challenge = compute_code_challenge("correct-verifier")
    assert verify_pkce("wrong-verifier", challenge, "S256") is False


def test_verify_pkce_rejects_unsupported_method():
    verifier = "some-verifier"
    challenge = compute_code_challenge(verifier)
    # "plain" is deliberately unsupported — PKCE without the hash step is not real protection.
    assert verify_pkce(verifier, challenge, "plain") is False


def test_compute_code_challenge_has_no_padding_and_is_urlsafe():
    challenge = compute_code_challenge("some-code-verifier-value")
    assert "=" not in challenge
    assert "+" not in challenge
    assert "/" not in challenge
