"""Authentication helpers: password hashing and signed session tokens.

Everything here is standard library. Passwords use PBKDF2-HMAC-SHA256.
Session tokens are `user_id.expiry.signature` signed with an HMAC secret so
they are stateless and tamper-evident (no server-side session store needed).
"""
import base64
import hashlib
import hmac
import os
import secrets
import time

# In a real deployment this comes from the environment / a secrets manager.
# Generated once per process if not supplied so tokens stay valid for a run.
SECRET = os.environ.get("TJP_SECRET", secrets.token_hex(32)).encode()

PBKDF2_ROUNDS = 240_000
TOKEN_TTL = 60 * 60 * 24 * 14  # 14 days


def hash_password(password: str, salt: str | None = None):
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), PBKDF2_ROUNDS)
    return base64.b64encode(dk).decode(), salt


def verify_password(password: str, pw_hash: str, salt: str) -> bool:
    candidate, _ = hash_password(password, salt)
    return hmac.compare_digest(candidate, pw_hash)


def _sign(msg: bytes) -> str:
    return base64.urlsafe_b64encode(hmac.new(SECRET, msg, hashlib.sha256).digest()).decode().rstrip("=")


def make_token(user_id: int) -> str:
    expiry = int(time.time()) + TOKEN_TTL
    payload = f"{user_id}.{expiry}".encode()
    return f"{user_id}.{expiry}.{_sign(payload)}"


def verify_token(token: str):
    """Return user_id if the token is valid and unexpired, else None."""
    try:
        uid, expiry, sig = token.split(".")
        payload = f"{uid}.{expiry}".encode()
        if not hmac.compare_digest(sig, _sign(payload)):
            return None
        if int(expiry) < int(time.time()):
            return None
        return int(uid)
    except (ValueError, AttributeError):
        return None
