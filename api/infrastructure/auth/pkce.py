import base64
import hashlib
import hmac


def verify_code_challenge(code_verifier: str, code_challenge: str) -> bool:
    """S256 only (RFC 7636 §4.2) — the plain method is deliberately not supported; this app never
    issues one and never needs to accept the weaker variant."""
    digest = hashlib.sha256(code_verifier.encode()).digest()
    computed = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return hmac.compare_digest(computed, code_challenge)
