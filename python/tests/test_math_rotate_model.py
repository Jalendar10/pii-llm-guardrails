from __future__ import annotations
import json
import pytest
from piiguard import decrypt_pii_in_text, init_from_password, unlock, rotate_password
from piiguard.generate import EncryptedGenerator, mock_llm_token_stream
from piiguard.pipeline import assert_no_plaintext_pii
from piiguard import model_pkg as mp
from piiguard.cli import main as cli

MATH = "Alice's SSN is 123-45-6789 and 2+2=4"


def _gen(keys, text):
    g = EncryptedGenerator(keys)
    out = "".join(g.on_token(t) for t in mock_llm_token_stream(text)) + g.finish()
    return out


def test_math_pii_roundtrip_on_token():
    k = init_from_password("math-pass-1234")
    out = _gen(k, MATH)
    assert "123-45-6789" not in out and "2+2=4" in out and "<PII:SSN:" in out
    assert_no_plaintext_pii(out)
    assert decrypt_pii_in_text(out, k) == MATH


def test_wrong_key_fails_closed():
    k = init_from_password("math-pass-1234")
    hdr = k.to_public_header()
    with pytest.raises(Exception):
        unlock("not-the-password", hdr)
    other = init_from_password("other-pass-5678")
    with pytest.raises(Exception):
        decrypt_pii_in_text(_gen(k, MATH), other)


def test_rotate_rewraps_same_dek():
    k = init_from_password("old-pass-1234")
    hdr = k.to_public_header()
    ct = _gen(k, MATH)
    new = rotate_password("old-pass-1234", "new-pass-5678", hdr)
    assert new["salt_b64"] != hdr["salt_b64"]
    assert new["wrapped_ciphertext_b64"] != hdr["wrapped_ciphertext_b64"]
    assert new["key_version"] == hdr["key_version"] and new["password_epoch"] == 2
    k2 = unlock("new-pass-5678", new)
    assert k2.dek == k.dek
    assert decrypt_pii_in_text(ct, k2) == MATH  # old ciphertext, new password
    with pytest.raises(Exception):
        unlock("old-pass-1234", new)
    with pytest.raises(Exception):
        rotate_password("bad-pass-0000", "x-new-pass-9", hdr)
    with pytest.raises(ValueError):
        rotate_password("old-pass-1234", "short", hdr)


def test_model_package_pull_run_decrypt_rotate(tmp_path, capsys):
    md, reg, um = tmp_path / "m", tmp_path / "r", tmp_path / "u"
    base = ["--models-dir", str(md), "--registry", str(reg)]
    ubase = ["--models-dir", str(um), "--registry", str(reg)]
    assert cli(base + ["model", "init", "demo", "--password", "pw-aaaa-1111"]) == 0
    files = {p.name for p in (md / "demo").iterdir()}
    assert files == {"manifest.json", "train_config.json", "weights.stub", "keyring.json"}
    assert b"pw-aaaa-1111" not in (md / "demo" / "weights.stub").read_bytes()
    assert "pw-aaaa-1111" not in (md / "demo" / "keyring.json").read_text()
    assert cli(base + ["model", "push", "demo"]) == 0
    assert cli(ubase + ["model", "pull", "demo"]) == 0
    capsys.readouterr()
    assert cli(ubase + ["run", "demo", "what is 3+4?", "--password", "pw-aaaa-1111"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["pii_encrypted"] and "3+4=7" in out["answer"] and "123-45-6789" not in out["answer"]
    assert cli(ubase + ["decrypt", "demo", out["answer"], "--password", "wrong-pw-9999"]) == 2
    assert "123-45-6789" not in capsys.readouterr().out
    w0 = mp.weights_digest("demo", um)
    assert cli(ubase + ["rotate", "demo", "--old-password", "pw-aaaa-1111", "--new-password", "pw-bbbb-2222"]) == 0
    assert mp.weights_digest("demo", um) == w0
    capsys.readouterr()
    assert cli(ubase + ["decrypt", "demo", out["answer"], "--password", "pw-bbbb-2222"]) == 0
    assert "123-45-6789" in capsys.readouterr().out
    assert cli(ubase + ["decrypt", "demo", out["answer"], "--password", "pw-aaaa-1111"]) == 2


@pytest.mark.parametrize("chunk", [1, 2, 3, 5, 7, 64])
@pytest.mark.parametrize("text", [
    MATH,
    "User email is jalendarreddy97@gmail.com and SSN is 123-45-6789 for records.",
    "Call 555 123 4567 or (555) 987-6543, host 10.0.0.12, mail bob@x.co.uk now",
    "alice@example.com",
])
def test_stream_exact_roundtrip_no_leak(chunk, text):
    k = init_from_password("stream-pass-1234")
    g = EncryptedGenerator(k)
    pieces = []
    for t in mock_llm_token_stream(text, chunk=chunk):
        pieces.append(g.on_token(t))
        assert_no_plaintext_pii("".join(pieces))
    pieces.append(g.finish())
    out = "".join(pieces)
    assert decrypt_pii_in_text(out, k) == text  # exact: no dup, no dropped chars
