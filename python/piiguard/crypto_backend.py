"""AES-256-GCM + Argon2id backend (pure Python). Swappable with Rust _pii_crypto."""

from __future__ import annotations

import os

from argon2.low_level import Type, hash_secret_raw
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def derive_argon2id(password: bytes, salt: bytes, m: int, t: int, p: int) -> bytes:
    # m is KiB for our Rust API
    return hash_secret_raw(
        secret=password,
        salt=salt,
        time_cost=t,
        memory_cost=m,
        parallelism=p,
        hash_len=32,
        type=Type.ID,
    )


def seal(key: bytes, plaintext: bytes, aad: bytes) -> tuple[int, bytes, bytes]:
    if len(key) != 32:
        raise ValueError("key must be 32 bytes")
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, plaintext, aad)
    return 1, nonce, ct


def open_sealed(key: bytes, version: int, nonce: bytes, ciphertext: bytes, aad: bytes) -> bytes:
    if version != 1:
        raise ValueError("unknown version")
    return AESGCM(key).decrypt(nonce, ciphertext, aad)


def wrap_dek(kek: bytes, key_version: int) -> tuple[int, bytes, bytes, bytes]:
    dek = os.urandom(32)
    nonce = os.urandom(12)
    # bind version in AAD
    aad = f"dek-wrap|{key_version}".encode()
    ct = AESGCM(kek).encrypt(nonce, dek, aad)
    return key_version, nonce, ct, dek


def unwrap_dek(kek: bytes, key_version: int, nonce: bytes, ciphertext: bytes) -> bytes:
    aad = f"dek-wrap|{key_version}".encode()
    return AESGCM(kek).decrypt(nonce, ciphertext, aad)
