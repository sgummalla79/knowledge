import base64
import hashlib

# RFC 7636 — the only method offered (`plain` is deliberately unsupported: it provides no
# protection against a code-interception attack, which is the entire point of PKCE).
SUPPORTED_CODE_CHALLENGE_METHOD = "S256"


def compute_code_challenge(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def verify_pkce(code_verifier: str, code_challenge: str, code_challenge_method: str) -> bool:
    if code_challenge_method != SUPPORTED_CODE_CHALLENGE_METHOD:
        return False
    return compute_code_challenge(code_verifier) == code_challenge
