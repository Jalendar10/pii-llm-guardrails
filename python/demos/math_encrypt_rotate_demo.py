"""One-shot demo: math + PII -> encrypt during generation -> decrypt -> wrong key
-> rotate password -> old ciphertext decrypts with new password -> old fails.
Run: python python/demos/math_encrypt_rotate_demo.py  (exit 0 == all PASS)
"""
from __future__ import annotations
import sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from piiguard import model_pkg as mp
from piiguard.keyring import unlock
from piiguard.pipeline import assert_no_plaintext_pii

PW, PW2, BAD = "train-time-pass-1", "rotated-pass-2!!", "wrong-password-x"
SSN, EMAIL = "123-45-6789", "alice@example.com"
results: list[tuple[str, bool]] = []

def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))

def fails(fn) -> bool:
    try:
        fn()
    except Exception:
        return True
    return False

with tempfile.TemporaryDirectory() as tmp:
    md, reg, users = Path(tmp) / "author_models", Path(tmp) / "registry", Path(tmp) / "user_models"
    name = "piiguard-math:stub"
    mp.init_model(name, PW, models_dir=md)
    mp.push(name, models_dir=md, registry=reg)
    mp.pull(name, models_dir=users, registry=reg)          # "ollama pull"
    print(f"pulled {name} -> {users / name}")
    w0 = mp.weights_digest(name, users)

    keys = unlock(PW, mp.load_header(name, users))           # operator/serve side
    out = mp.run(name, "What is 2+2?", keys, models_dir=users)  # "ollama run"
    ans = out["answer"]
    print("prompt : What is 2+2?")
    print("output :", ans)
    check("math intact in encrypted output", "2+2=4" in ans)
    check("encrypt (no plaintext PII, tokens present)",
          SSN not in ans and EMAIL not in ans and ans.count("<PII:") == 2
          and not fails(lambda: assert_no_plaintext_pii(ans)))

    plain = mp.decrypt(name, ans, PW, models_dir=users)
    print("decrypt:", plain)
    expected = f"Alice's SSN is {SSN}, email {EMAIL}, and 2+2=4."
    check("decrypt with correct password (0 data loss)", plain == expected)
    check("wrong password fails closed", fails(lambda: mp.decrypt(name, ans, BAD, models_dir=users)))

    hdr = mp.rotate(name, PW, PW2, models_dir=users)
    print(f"rotated password -> password_epoch={hdr['password_epoch']}")
    check("rotate: weights unchanged", mp.weights_digest(name, users) == w0)
    check("rotate: wrong old password rejected", fails(lambda: mp.rotate(name, BAD, "another-pass-3", models_dir=users)))
    check("post-rotate: OLD ciphertext decrypts with NEW password",
          mp.decrypt(name, ans, PW2, models_dir=users) == expected)
    check("post-rotate: old password fails closed", fails(lambda: mp.decrypt(name, ans, PW, models_dir=users)))
    keys2 = unlock(PW2, mp.load_header(name, users))
    out2 = mp.run(name, "What is 7*6?", keys2, models_dir=users)
    check("post-rotate: new generation works (7*6=42)",
          "7*6=42" in out2["answer"] and SSN not in out2["answer"]
          and SSN in mp.decrypt(name, out2["answer"], PW2, models_dir=users))

n_ok = sum(ok for _, ok in results)
print(f"\nSUMMARY: {n_ok}/{len(results)} PASS")
sys.exit(0 if n_ok == len(results) else 1)
