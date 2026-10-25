"""PII guardrails — encrypt during LLM token generation."""

__version__ = "0.1.0"

try:
    from _pii_crypto import (  # type: ignore
        derive_argon2id,
        open as crypto_open,
        seal,
        unwrap_dek,
        wrap_dek,
    )
except ImportError:
    from .crypto_backend import derive_argon2id, seal, unwrap_dek, wrap_dek
    from .crypto_backend import open_sealed as crypto_open

open = crypto_open

from .detect import detect
from .generate import EncryptedGenerator, generate_tokens_encrypted
from .keyring import init_from_password, rotate_password, unlock
from .pipeline import (
    assert_no_plaintext_pii,
    decrypt_pii_in_text,
    encrypt_pii_in_text,
    strip_unverified_tokens,
    verify_pii_tokens,
)
from .serve import build_response

__all__ = [
    "__version__",
    "seal",
    "open",
    "derive_argon2id",
    "wrap_dek",
    "unwrap_dek",
    "detect",
    "init_from_password",
    "unlock",
    "rotate_password",
    "encrypt_pii_in_text",
    "decrypt_pii_in_text",
    "assert_no_plaintext_pii",
    "EncryptedGenerator",
    "generate_tokens_encrypted",
    "verify_pii_tokens",
    "strip_unverified_tokens",
    "build_response",
]
