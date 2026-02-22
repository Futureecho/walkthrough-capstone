"""Fernet symmetric encryption for API keys stored in OwnerSettings."""

from __future__ import annotations

import os
from cryptography.fernet import Fernet

_FERNET_KEY = os.environ.get("FERNET_KEY", "")


def _get_fernet() -> Fernet:
    if not _FERNET_KEY:
        raise RuntimeError("FERNET_KEY environment variable not set. Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"")
    return Fernet(_FERNET_KEY.encode("utf-8") if isinstance(_FERNET_KEY, str) else _FERNET_KEY)


def encrypt_value(plain: str) -> str:
    if not plain:
        return ""
    return _get_fernet().encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_value(encrypted: str) -> str:
    if not encrypted:
        return ""
    return _get_fernet().decrypt(encrypted.encode("utf-8")).decode("utf-8")


def encrypt_bytes(data: bytes) -> bytes:
    if not data:
        return b""
    return _get_fernet().encrypt(data)


def decrypt_bytes(data: bytes) -> bytes:
    if not data:
        return b""
    return _get_fernet().decrypt(data)
