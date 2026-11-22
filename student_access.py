"""Hashed PIN helpers for learner access. PINs are never stored in plaintext."""
import hashlib
import hmac
import re
import secrets

_ITERATIONS = 240_000
_SALT_BYTES = 16


def make_pin_record(pin):
    pin = str(pin or "")
    if not re.fullmatch(r"\d{6}", pin):
        raise ValueError("PIN must contain exactly 6 digits.")
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, _ITERATIONS)
    return {
        "salt": salt.hex(),
        "hash": digest.hex(),
        "iterations": _ITERATIONS,
    }


def verify_pin(pin, record):
    if not isinstance(record, dict):
        return False
    salt_hex = record.get("salt", "")
    hash_hex = record.get("hash", "")
    iterations = record.get("iterations", _ITERATIONS)
    if (not isinstance(salt_hex, str) or not re.fullmatch(r"[0-9a-f]{32}", salt_hex)
            or not isinstance(hash_hex, str) or not re.fullmatch(r"[0-9a-f]{64}", hash_hex)
            or not isinstance(iterations, int) or iterations < 100_000 or iterations > 500_000):
        return False
    if not re.fullmatch(r"\d{6}", str(pin or "")):
        return False
    candidate = hashlib.pbkdf2_hmac(
        "sha256", str(pin).encode("utf-8"), bytes.fromhex(salt_hex), iterations
    ).hex()
    return hmac.compare_digest(candidate, hash_hex)
