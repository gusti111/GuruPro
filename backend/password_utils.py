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
    """Return (valid, legacy_plaintext), rejecting malformed or excessive work factors."""
    if not isinstance(password, str) or not isinstance(stored_value, str):
        return False, False
    if not stored_value.startswith(ALGORITHM + "$"):
        return hmac.compare_digest(password.encode("utf-8"), stored_value.encode("utf-8")), True
    try:
        algorithm, iterations_text, salt_hex, digest_hex = stored_value.split("$", 3)
        iterations = int(iterations_text)
        if algorithm != ALGORITHM or not (100_000 <= iterations <= 1_000_000):
            return False, False
        if len(salt_hex) != SALT_BYTES * 2 or len(digest_hex) != 64:
            return False, False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, iterations, dklen=32
        )
        return hmac.compare_digest(candidate, expected), False
    except (ValueError, TypeError):
        return False, False
