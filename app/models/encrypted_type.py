"""SQLAlchemy TypeDecorator for transparent Fernet encryption of string columns."""

from __future__ import annotations

from sqlalchemy import String, TypeDecorator


class EncryptedString(TypeDecorator):
    """Encrypts on write, decrypts on read. Falls back to plaintext if decryption fails."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None or value == "":
            return value
        from app.services.encryption import encrypt_value
        try:
            return encrypt_value(value)
        except RuntimeError:
            # FERNET_KEY not set — store plaintext (dev mode)
            return value

    def process_result_value(self, value, dialect):
        if value is None or value == "":
            return value
        from app.services.encryption import decrypt_value
        try:
            return decrypt_value(value)
        except Exception:
            # Decryption failed — probably pre-existing plaintext data
            return value
