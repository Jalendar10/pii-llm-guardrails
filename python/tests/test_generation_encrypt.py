"""PII must be encrypted during token generation — never emitted plaintext mid-stream."""

from __future__ import annotations

import pytest

from piiguard import (
    decrypt_pii_in_text,
    init_from_password,
)
from piiguard.generate import EncryptedGenerator, generate_tokens_encrypted, mock_llm_token_stream
from piiguard.pipeline import assert_no_plaintext_pii


PLAIN = (
    "User email is jalendarreddy97@gmail.com and SSN is 123-45-6789 for records."
)


def test_generation_stream_never_emits_plaintext_pii():
    keys = init_from_password("gen-time-secret-key")
    emitted = []
    for piece in generate_tokens_encrypted(mock_llm_token_stream(PLAIN, chunk=1), keys):
        emitted.append(piece)
        # At every step of generation, cumulative public output has no PII
        assert_no_plaintext_pii("".join(emitted))
        assert "jalendarreddy97@gmail.com" not in "".join(emitted)
        assert "123-45-6789" not in "".join(emitted)

    full = "".join(emitted)
    assert "<PII:EMAIL:" in full
    assert "<PII:SSN:" in full
    restored = decrypt_pii_in_text(full, keys)
    assert "jalendarreddy97@gmail.com" in restored
    assert "123-45-6789" in restored


def test_on_token_hook_inside_loop():
    keys = init_from_password("hook-secret-key!!")
    gen = EncryptedGenerator(keys)
    # Simulate model.generate() loop
    public = []
    for tok in mock_llm_token_stream(PLAIN, chunk=3):
        public.append(gen.on_token(tok))
        assert "jalendarreddy97@gmail.com" not in "".join(public)
    public.append(gen.finish())
    out = "".join(public)
    assert_no_plaintext_pii(out)
    assert decrypt_pii_in_text(out, keys).count("@") == 1


def test_wrong_key_cannot_decrypt_generation_output():
    keys = init_from_password("right-key-here!!")
    out = "".join(generate_tokens_encrypted(mock_llm_token_stream(PLAIN), keys))
    other = init_from_password("wrong-key-here!!")
    with pytest.raises(Exception):
        decrypt_pii_in_text(out, other)
