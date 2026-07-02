"""
PREDAIOT Security Layer — encryption at rest + tamper-evident audit trail.

Isolated from main.py so it can be code-reviewed and tested independently.
Public surface:

    SecretResolver          Protocol — implementations resolve secrets by name.
    EnvSecretResolver       Env-var implementation (interim).
    VaultSecretResolver     Placeholder — future HashiCorp Vault integration.
    DataProtector           Fernet + PBKDF2 encryption for field-level protection.
    hash_chain_next()       Compute the next hash in a tamper-evident chain.
    verify_hash_chain()     Walk a chain of records and report first break.

All errors log without leaking plaintext. All comparisons on hashes use
constant-time equality to prevent timing attacks.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
from typing import Optional, Protocol, Iterable, Any, Tuple

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger("predaiot.security")

# PBKDF2 iterations. 480,000 is the current OWASP recommendation for SHA-256
# (as of 2023–2024). Increase over time as hardware gets faster.
_PBKDF2_ITERS = 480_000

# Static salt is *okay* for a single-tenant deployment because the master key
# is unique per environment. For multi-tenant, this should be a per-tenant
# random salt stored alongside the ciphertext. Explicitly parameterised.
_DEFAULT_SALT = b"predaiot-static-v1-change-in-multitenant"


# ══════════════════════════════════════════════════════════════════════
# Secret resolution — pluggable backend
# ══════════════════════════════════════════════════════════════════════
class SecretResolver(Protocol):
    """Resolves secret values by logical name. Return None if not set."""

    def get(self, name: str) -> Optional[str]:
        ...


class EnvSecretResolver:
    """
    Environment-variable resolver — the pragmatic interim choice.
    Render's env-var dashboard is the store; this reads it.
    """

    def get(self, name: str) -> Optional[str]:
        val = os.environ.get(name)
        # Never log the value itself. Only whether it was present.
        if not val:
            logger.warning("secret_missing", extra={"secret_name": name})
            return None
        return val


class VaultSecretResolver:
    """
    Placeholder for HashiCorp Vault. Not implemented — raises to force the
    switch to be a deliberate infrastructure decision, not an accidental
    fallback. The interface is what matters: swapping this in later is a
    one-line change at the call site.
    """

    def __init__(self, vault_addr: str, token: str, mount_path: str = "secret"):
        self.vault_addr  = vault_addr
        self.token       = token
        self.mount_path  = mount_path

    def get(self, name: str) -> Optional[str]:  # pragma: no cover
        raise NotImplementedError(
            "VaultSecretResolver not wired yet. Add hvac to requirements + "
            "implement here. Kept as a placeholder so callers can be Vault-"
            "ready today without waiting for the Vault deployment."
        )


# ══════════════════════════════════════════════════════════════════════
# DataProtector — Fernet encryption for column-level protection
# ══════════════════════════════════════════════════════════════════════
class DataProtector:
    """
    Symmetric encryption for sensitive fields at rest. Fernet under the hood
    (AES-128-CBC + HMAC-SHA-256) with a PBKDF2-derived key.

    Master key is read via a SecretResolver — env-var today, Vault tomorrow.
    Never logs plaintext, never logs the master key. Decryption failure
    returns None rather than raising, so a tampered row can't crash the
    audit endpoint (it just fails to decrypt and the caller sees None).
    """

    _MASTER_KEY_ENV = "PREDAIOT_MASTER_KEY"

    def __init__(
        self,
        resolver: Optional[SecretResolver] = None,
        salt: bytes = _DEFAULT_SALT,
        _test_key: Optional[str] = None,  # only used by tests
    ):
        resolver = resolver or EnvSecretResolver()
        master_key = _test_key or resolver.get(self._MASTER_KEY_ENV)
        if not master_key:
            raise ValueError(
                f"CRITICAL: {self._MASTER_KEY_ENV} not set. "
                "Refusing to start with unencrypted-at-rest data. "
                "Generate a strong random value (`python -c \"import secrets;"
                "print(secrets.token_urlsafe(48))\"`) and set it on Render."
            )
        if len(master_key) < 32:
            raise ValueError(
                "CRITICAL: master key is too short (< 32 chars). "
                "Use at least 256 bits of entropy."
            )

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=_PBKDF2_ITERS,
        )
        key = base64.urlsafe_b64encode(kdf.derive(master_key.encode("utf-8")))
        self._cipher = Fernet(key)

    def encrypt(self, plaintext: Optional[str]) -> Optional[str]:
        """Encrypt UTF-8 text. Returns URL-safe base64 ciphertext. None → None."""
        if plaintext is None:
            return None
        if not isinstance(plaintext, str):
            plaintext = str(plaintext)
        try:
            return self._cipher.encrypt(plaintext.encode("utf-8")).decode("utf-8")
        except Exception as e:
            # Log the error class but not the plaintext.
            logger.error("encrypt_failed", extra={"error_class": type(e).__name__})
            raise

    def decrypt(self, ciphertext: Optional[str]) -> Optional[str]:
        """Decrypt. Returns None on invalid / tampered / expired token."""
        if not ciphertext:
            return None
        try:
            return self._cipher.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            # Tampered or wrong key. Do NOT reveal which via error message.
            logger.warning("decrypt_invalid_token")
            return None
        except Exception as e:
            logger.error("decrypt_failed", extra={"error_class": type(e).__name__})
            return None


# ══════════════════════════════════════════════════════════════════════
# Hash chain — tamper-evident audit trail (ISO 27001 A.12.4)
# ══════════════════════════════════════════════════════════════════════
_GENESIS_HASH = "GENESIS"


def hash_chain_next(previous_hash: str, canonical_content: str) -> str:
    """
    Compute the next hash in a chain. previous_hash links to the row that
    came before; canonical_content is a stable string derived from THIS
    row's fields (timestamp + user + action + ...).

    SHA-256 is used because it's the ISO auditor's default expectation.
    Change here only if you also migrate the whole existing chain.
    """
    data = f"{previous_hash}|{canonical_content}".encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def hashes_equal(a: str, b: str) -> bool:
    """Constant-time hash comparison — prevents timing-based tamper probes."""
    return hmac.compare_digest((a or "").encode("utf-8"),
                               (b or "").encode("utf-8"))


def verify_hash_chain(rows: Iterable[Any]) -> Tuple[bool, Optional[int], str]:
    """
    Walk an ordered iterable of chain rows and verify:
      1. row[0].previous_hash == GENESIS
      2. row[i].current_hash  == hash_chain_next(row[i].previous_hash, row[i].canonical())
      3. row[i+1].previous_hash == row[i].current_hash

    Each row must expose:
      - previous_hash: str
      - current_hash:  str
      - canonical(): str    (implemented on the SQLAlchemy model)

    Returns (ok, first_broken_row_index_or_None, message).
    """
    prev_current = _GENESIS_HASH
    for i, row in enumerate(rows):
        expected_prev = prev_current
        if not hashes_equal(row.previous_hash or "", expected_prev):
            return (False, i,
                    f"chain break at row {i}: previous_hash != expected "
                    f"(expected the previous row's current_hash)")

        recomputed = hash_chain_next(row.previous_hash, row.canonical())
        if not hashes_equal(row.current_hash or "", recomputed):
            return (False, i,
                    f"chain break at row {i}: current_hash does not match "
                    "recomputed value — row was modified after insertion")

        prev_current = row.current_hash

    return (True, None, "chain intact")
