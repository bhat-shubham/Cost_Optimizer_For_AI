"""
API key hashing utilities.

Security notes:
  • SHA-256 is used for key hashing — acceptable for API keys because
    they are high-entropy random strings (not low-entropy passwords).
    bcrypt/argon2 would be overkill and add latency to every request.
  • Raw keys use the sk_live_ prefix (convention, not security).
  • generate_api_key() returns the raw key exactly once — the caller
    must display it to the user immediately. It is never stored.
"""

import hashlib
import secrets


_KEY_PREFIX = "sk_live_"


def hash_api_key(raw_key: str) -> str:
    """
    Hash a raw API key using SHA-256.

    Returns the hex digest string for storage/lookup.
    """
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_api_key() -> tuple[str, str]:
    """
    Generate a new API key.

    Returns:
        (raw_key, key_hash) — raw_key is shown once, key_hash is stored.
    """
    random_part = secrets.token_hex(32)  # 64 hex chars = 256 bits
    raw_key = f"{_KEY_PREFIX}{random_part}"
    key_hash = hash_api_key(raw_key)
    return raw_key, key_hash
