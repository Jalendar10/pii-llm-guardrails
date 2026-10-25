from __future__ import annotations
import json, secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from . import derive_argon2id, unwrap_dek, wrap_dek

SALT_LEN = 16
ARGON2_M = 19 * 1024
ARGON2_T = 2
ARGON2_P = 1

def _b64(b: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(b).decode("ascii")

def _unb64(s: str) -> bytes:
    import base64
    return base64.urlsafe_b64decode(s.encode("ascii"))

@dataclass
class KeyMaterial:
    salt: bytes
    kek: bytes
    dek: bytes
    key_version: int
    wrapped_nonce: bytes
    wrapped_ciphertext: bytes
    m: int
    t: int
    p: int
    def to_public_header(self) -> dict[str, Any]:
        return {
            "salt_b64": _b64(self.salt),
            "key_version": self.key_version,
            "wrapped_nonce_b64": _b64(self.wrapped_nonce),
            "wrapped_ciphertext_b64": _b64(self.wrapped_ciphertext),
            "argon2": {"m": self.m, "t": self.t, "p": self.p},
        }

def init_from_password(password: str, *, key_version: int = 1) -> KeyMaterial:
    if not password or len(password) < 8:
        raise ValueError("password must be at least 8 characters")
    salt = secrets.token_bytes(SALT_LEN)
    kek = derive_argon2id(password.encode(), salt, ARGON2_M, ARGON2_T, ARGON2_P)
    version, nonce, wrapped, dek = wrap_dek(kek, key_version)
    return KeyMaterial(salt, kek, dek, version, nonce, wrapped, ARGON2_M, ARGON2_T, ARGON2_P)

def unlock(password: str, header: dict[str, Any]) -> KeyMaterial:
    salt = _unb64(header["salt_b64"])
    argon = header["argon2"]
    kek = derive_argon2id(password.encode(), salt, int(argon["m"]), int(argon["t"]), int(argon["p"]))
    dek = unwrap_dek(kek, int(header["key_version"]), _unb64(header["wrapped_nonce_b64"]), _unb64(header["wrapped_ciphertext_b64"]))
    return KeyMaterial(salt, kek, dek, int(header["key_version"]), _unb64(header["wrapped_nonce_b64"]), _unb64(header["wrapped_ciphertext_b64"]), int(argon["m"]), int(argon["t"]), int(argon["p"]))


def rotate_password(old_password: str, new_password: str, header: dict[str, Any]) -> dict[str, Any]:
    """Rewrap the SAME DEK under a KEK derived from `new_password` (fresh salt).

    No ciphertext is re-encrypted: data tokens are sealed with the DEK, and the
    DEK (and its `key_version`, which is bound into data AAD) is unchanged.
    Only the wrapped-DEK envelope + salt change. The old password stops working
    because the old wrapped blob/salt are discarded. Fails closed (raises) if
    `old_password` is wrong.
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    import os

    if not new_password or len(new_password) < 8:
        raise ValueError("password must be at least 8 characters")
    if new_password == old_password:
        raise ValueError("new password must differ from old password")
    km = unlock(old_password, header)  # raises InvalidTag on wrong password
    salt = secrets.token_bytes(SALT_LEN)
    kek = derive_argon2id(new_password.encode(), salt, ARGON2_M, ARGON2_T, ARGON2_P)
    nonce = os.urandom(12)
    wrapped = AESGCM(kek).encrypt(nonce, km.dek, f"dek-wrap|{km.key_version}".encode())
    new = KeyMaterial(salt, kek, km.dek, km.key_version, nonce, wrapped, ARGON2_M, ARGON2_T, ARGON2_P)
    out = new.to_public_header()
    out["password_epoch"] = int(header.get("password_epoch", 1)) + 1
    return out
