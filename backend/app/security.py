from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, status


class EncryptionConfigurationError(RuntimeError):
    pass


def mask_secret(secret: str | None) -> str:
    if not secret:
        return "Not configured"
    if len(secret) <= 4:
        return "*" * len(secret)
    return f"{secret[:2]}{'*' * (len(secret) - 4)}{secret[-2:]}"


def get_encrypter() -> Fernet:
    key = os.environ.get("PROXY_ENCRYPTION_KEY")
    if not key:
        raise EncryptionConfigurationError(
            "PROXY_ENCRYPTION_KEY is required for database-backed credentials."
        )
    return Fernet(key.encode("ascii"))


def encrypt_secret(secret: str) -> tuple[str, str]:
    token = get_encrypter().encrypt(secret.encode("utf-8")).decode("utf-8")
    return token, mask_secret(secret)


def decrypt_secret(token: str) -> str:
    try:
        return get_encrypter().decrypt(token.encode("utf-8")).decode("utf-8")
    except EncryptionConfigurationError:
        raise
    except InvalidToken as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stored credential could not be decrypted.",
        ) from exc
