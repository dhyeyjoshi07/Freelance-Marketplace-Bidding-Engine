"""
Data encryption service (DBMS Unit 9: Data Security).

Implements AES-256 column-level encryption for sensitive data fields.
This demonstrates discretionary access control at the data layer —
even if the database is compromised, encrypted columns remain unreadable
without the application-level key.

Architecture:
    Application           Database
    ┌─────────┐           ┌──────────┐
    │ encrypt()│──────────▶│ ciphertext│
    │ decrypt()│◀──────────│ (stored) │
    └─────────┘           └──────────┘

    The encryption key never leaves the application process.
    MySQL stores only the encrypted bytes (base64-encoded).

Usage:
    from backend.services.encryption import encrypt, decrypt
    encrypted_email = encrypt("alice@dev.io")    # "gAAAAABm..."
    original_email  = decrypt(encrypted_email)    # "alice@dev.io"
"""

import base64
import hashlib

from cryptography.fernet import Fernet

from backend.config import ENCRYPTION_KEY


def _derive_fernet_key(passphrase: str) -> bytes:
    """
    Derive a 32-byte Fernet-compatible key from an arbitrary passphrase.

    Fernet requires a URL-safe base64-encoded 32-byte key.  We use SHA-256
    to hash the passphrase into exactly 32 bytes, then base64-encode it.
    This is a simplified KDF — production systems should use PBKDF2 or Argon2.
    """
    key_bytes = hashlib.sha256(passphrase.encode()).digest()
    return base64.urlsafe_b64encode(key_bytes)


# Singleton cipher instance, initialized once at module load
_fernet = Fernet(_derive_fernet_key(ENCRYPTION_KEY))


def encrypt(plaintext: str) -> str:
    """
    Encrypt a plaintext string using AES-256 (via Fernet).

    Returns a base64-encoded ciphertext string suitable for storage
    in a VARCHAR/TEXT column.

    Args:
        plaintext: The sensitive data to encrypt.

    Returns:
        Base64-encoded ciphertext string.
    """
    if not plaintext:
        return plaintext
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """
    Decrypt a ciphertext string back to plaintext.

    Args:
        ciphertext: The base64-encoded encrypted string from the database.

    Returns:
        Original plaintext string.

    Raises:
        cryptography.fernet.InvalidToken: If the key is wrong or data is tampered.
    """
    if not ciphertext:
        return ciphertext
    return _fernet.decrypt(ciphertext.encode()).decode()
