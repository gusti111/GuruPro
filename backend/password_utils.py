"""PBKDF2 password helpers for GuruPro Firestore account records."""
import hashlib
import hmac
import secrets

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 600_000
SALT_BYTES = 16


def hash_password(password: str) -> str:
    """Return a salted PBKDF2 hash in a versioned, self-describing format."""
    if not isinstance(password, str) or not password:
        raise ValueError("Password must be a non-empty string")
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return ALGORITHM + "$" + str(ITERATIONS) + "$" + salt.hex() + "$" + digest.hex()


def verify_password(password: str, stored_value: str) -> tuple[bool, bool]:
    """Return (valid, legacy_plaintext); legacy support enables login migration."""
    if not isinstance(password, str) or not isinstance(stored_value, str):
        return False, False
    if not stored_value.startswith(ALGORITHM + "$"):
        return hmac.compare_digest(password, stored_value), True
    try:
        algorithm, iterations, salt_hex, digest_hex = stored_value.split("$", 3)
        if algorithm != ALGORITHM:
            return False, False
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
        ).hex()
        return hmac.compare_digest(candidate, digest_hex), False
    except (ValueError, TypeError):
        return False, False
