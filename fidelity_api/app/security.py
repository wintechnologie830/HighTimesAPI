import hashlib
import hmac
import os

PBKDF2_ITERATIONS = 390_000


def hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return digest.hex(), salt.hex()


def verify_password(password: str, salt_hex: str, expected_hash_hex: str) -> bool:
    digest_hex, _ = hash_password(password, bytes.fromhex(salt_hex))
    return hmac.compare_digest(digest_hex, expected_hash_hex)
