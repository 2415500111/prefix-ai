"""Field-level encryption for PII and keyed blind indexes for looking it up.

Ciphertext format: ``enc:v1:<key-id>:<base64url(nonce || ciphertext+tag)>``.
Each value is bound to its column through AES-GCM associated data, so a ciphertext
copied into a different column fails to decrypt.
"""

import base64
import binascii
import hashlib
import hmac
import os
import re
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from prefix_api.core.config import Settings, get_settings

_PREFIX = "enc:v1:"
_NONCE_BYTES = 12
_KEY_BYTES = 32
_KEY_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,32}$")


class CryptoError(Exception):
    """Raised when a key is misconfigured or a ciphertext cannot be decrypted."""


def _b64decode(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(padded)
    except (binascii.Error, ValueError) as exc:
        raise CryptoError("Invalid base64 data") from exc


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def generate_key() -> str:
    """Return a new random key in the base64 form expected by PII_ENCRYPTION_KEYS."""
    return _b64encode(os.urandom(_KEY_BYTES))


@dataclass(frozen=True, slots=True)
class FieldCipher:
    active_key_id: str
    keys: dict[str, AESGCM]

    @classmethod
    def from_entries(cls, entries: list[str]) -> FieldCipher:
        if not entries:
            raise CryptoError("At least one encryption key is required")
        keys: dict[str, AESGCM] = {}
        for entry in entries:
            key_id, sep, encoded = entry.partition(":")
            if not sep or not _KEY_ID_PATTERN.match(key_id):
                raise CryptoError("Encryption keys must look like '<key-id>:<base64 key>'")
            raw = _b64decode(encoded)
            if len(raw) != _KEY_BYTES:
                raise CryptoError(f"Encryption key '{key_id}' must be {_KEY_BYTES} bytes")
            if key_id in keys:
                raise CryptoError(f"Duplicate encryption key id '{key_id}'")
            keys[key_id] = AESGCM(raw)
        return cls(active_key_id=entries[0].partition(":")[0], keys=keys)

    def encrypt(self, plaintext: str, context: str) -> str:
        nonce = os.urandom(_NONCE_BYTES)
        sealed = self.keys[self.active_key_id].encrypt(
            nonce, plaintext.encode("utf-8"), context.encode("utf-8")
        )
        return f"{_PREFIX}{self.active_key_id}:{_b64encode(nonce + sealed)}"

    def decrypt(self, token: str, context: str) -> str:
        if not token.startswith(_PREFIX):
            raise CryptoError("Value is not an encrypted field")
        key_id, sep, payload = token.removeprefix(_PREFIX).partition(":")
        if not sep:
            raise CryptoError("Malformed encrypted field")
        key = self.keys.get(key_id)
        if key is None:
            raise CryptoError(f"Unknown encryption key id '{key_id}'")
        raw = _b64decode(payload)
        nonce, sealed = raw[:_NONCE_BYTES], raw[_NONCE_BYTES:]
        try:
            return key.decrypt(nonce, sealed, context.encode("utf-8")).decode("utf-8")
        except InvalidTag as exc:
            raise CryptoError("Encrypted field failed authentication") from exc

    def needs_rotation(self, token: str) -> bool:
        return not token.startswith(f"{_PREFIX}{self.active_key_id}:")


@dataclass(frozen=True, slots=True)
class BlindIndexer:
    key: bytes

    def index(self, value: str, context: str) -> str:
        message = f"{context}\x00{value}".encode()
        return hmac.new(self.key, message, hashlib.sha256).hexdigest()


def normalize_email(email: str) -> str:
    return email.strip().lower()


def normalize_phone(phone: str) -> str:
    """Reduce an E.164 number to '+' and digits so formatting differences still match."""
    digits = re.sub(r"\D", "", phone)
    return f"+{digits}"


def normalize_identifier(value: str) -> str:
    return value.strip().upper()


@dataclass(slots=True)
class _CryptoState:
    cipher: FieldCipher | None = None
    indexer: BlindIndexer | None = None


_state = _CryptoState()


def configure_crypto(settings: Settings) -> None:
    """Load keys from settings. Called at API and worker startup, and by tests."""
    _state.cipher = FieldCipher.from_entries(
        [entry.get_secret_value() for entry in settings.pii_encryption_keys]
    )
    _state.indexer = BlindIndexer(key=settings.pii_blind_index_key.get_secret_value().encode())


def get_field_cipher() -> FieldCipher:
    if _state.cipher is None:
        configure_crypto(get_settings())
    if _state.cipher is None:  # pragma: no cover - configure_crypto always sets it
        raise CryptoError("Field encryption is not configured")
    return _state.cipher


def get_blind_indexer() -> BlindIndexer:
    if _state.indexer is None:
        configure_crypto(get_settings())
    if _state.indexer is None:  # pragma: no cover - configure_crypto always sets it
        raise CryptoError("Blind indexing is not configured")
    return _state.indexer
