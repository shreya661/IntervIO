"""
Security utilities — Fernet symmetric encryption for candidate PII.

All candidate names, resume text, answers, and biometric telemetry are encrypted
before storing in memory or at rest.
The encryption key is loaded from INTERVIEW_ENCRYPTION_KEY in .env/environment
or generated as a persistent Fernet key.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Ensure .env is loaded
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH)
else:
    load_dotenv()

logger = logging.getLogger("person3.security")

try:
    from cryptography.fernet import Fernet
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False
    logger.warning(
        "cryptography package not installed. PII will not be encrypted. "
        "Run: pip install cryptography"
    )


# ── Key management ──────────────────────────────────────────────────────────

def _load_or_generate_key() -> bytes:
    """
    Load encryption key from INTERVIEW_ENCRYPTION_KEY env var, or generate
    a fresh ephemeral key for this server session.
    """
    env_key = os.environ.get("INTERVIEW_ENCRYPTION_KEY", "").strip()
    if env_key:
        try:
            # Validate the key is well-formed
            Fernet(env_key.encode())
            logger.info("Loaded persistent encryption key from INTERVIEW_ENCRYPTION_KEY.")
            return env_key.encode()
        except Exception:
            logger.warning("INTERVIEW_ENCRYPTION_KEY is malformed. Generating a new key.")

    key = Fernet.generate_key()
    logger.info(
        "Generated ephemeral Fernet encryption key. "
        "Set INTERVIEW_ENCRYPTION_KEY in .env to persist across restarts."
    )
    return key


if _AVAILABLE:
    _KEY = _load_or_generate_key()
    _FERNET = Fernet(_KEY)
else:
    _KEY = None
    _FERNET = None


# ── Public API ────────────────────────────────────────────────────────────────

def is_encryption_active() -> bool:
    """Check if AES-256 Fernet encryption is active and ready."""
    return bool(_AVAILABLE and _FERNET is not None)


def encrypt(plaintext: str) -> str:
    """
    Encrypt a UTF-8 string and return a base64-encoded ciphertext string.
    Falls back to identity (no-op) if cryptography is not available.
    """
    if not _AVAILABLE or _FERNET is None:
        return plaintext  # no-op fallback
    if not isinstance(plaintext, str):
        plaintext = str(plaintext)
    token = _FERNET.encrypt(plaintext.encode("utf-8"))
    return base64.urlsafe_b64encode(token).decode("ascii")


def decrypt(ciphertext: str) -> str:
    """
    Decrypt a ciphertext produced by encrypt().
    Falls back to returning the input unchanged if cryptography is not available.
    """
    if not _AVAILABLE or _FERNET is None:
        return ciphertext  # no-op fallback
    try:
        raw = base64.urlsafe_b64decode(ciphertext.encode("ascii"))
        return _FERNET.decrypt(raw).decode("utf-8")
    except Exception as exc:
        logger.error("Decryption failed: %s", exc)
        return "[decryption error]"


def encrypt_json(data: Any) -> str:
    """Serialize data to JSON and encrypt with Fernet."""
    serialized = json.dumps(data, default=str)
    return encrypt(serialized)


def decrypt_json(ciphertext: str) -> Any:
    """Decrypt a ciphertext and parse back from JSON."""
    decrypted_str = decrypt(ciphertext)
    if decrypted_str == "[decryption error]":
        return None
    try:
        return json.loads(decrypted_str)
    except Exception:
        return decrypted_str


def mask(value: str, visible_chars: int = 3) -> str:
    """Return a safely masked version for logging (e.g. 'Ale***')."""
    if not value:
        return "***"
    if len(value) <= visible_chars:
        return "*" * len(value)
    return value[:visible_chars] + "*" * (len(value) - visible_chars)


# ── PII Sanitizer for External AI / LLMs ──────────────────────────────────────

_EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b")
_PHONE_REGEX = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
_SSN_REGEX = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_ADDR_REGEX = re.compile(
    r"\b\d{1,5}\s+[A-Za-z0-9\s.,]{3,35}\s+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Court|Ct|Way|Plaza|Pl|Terrace|Ter|Parkway|Pkwy|Circle|Cir|Highway|Hwy)\b",
    re.IGNORECASE
)


def scrub_pii_for_llm(text: str) -> str:
    """
    Pre-flight PII scrubber that strips personal identifying details
    (email addresses, phone numbers, government IDs, physical street addresses)
    before transmitting prompts to external third-party LLM APIs (e.g. Google Gemini).
    """
    if not text or not isinstance(text, str):
        return text or ""
    
    sanitized = _EMAIL_REGEX.sub("[REDACTED_EMAIL]", text)
    sanitized = _PHONE_REGEX.sub("[REDACTED_PHONE]", sanitized)
    sanitized = _SSN_REGEX.sub("[REDACTED_ID]", sanitized)
    sanitized = _ADDR_REGEX.sub("[REDACTED_ADDRESS]", sanitized)
    return sanitized
