"""Real HF model (Qwen3) -> encrypt PII *during* generation -> decrypt roundtrip.

The model streams tokens (TextIteratorStreamer, worker thread); each chunk goes
through EncryptedGenerator.on_token, which seals grounded PII with the live DEK
before it is released. Same serve path as the stub: injection scan, grounding
gate, fake-token stripping, DEK verification, JSON validation.

CPU smoke (box):   python demos/qwen_sealed_demo.py --model-id Qwen/Qwen3-0.6B
Real target (GPU/MPS): python demos/qwen_sealed_demo.py --model-id Qwen/Qwen3-8B
Exit 0 == every safety check PASSed.
"""
from __future__ import annotations

import argparse, json, os, resource, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from piiguard import model_pkg as mp
from piiguard.hf_backend import DEFAULT_MODEL_ID, HFBackend
from piiguard.keyring import unlock
from piiguard.pipeline import _TOKEN_RE, assert_no_plaintext_pii

EMAIL, SSN = "alice@example.com", "123-45-6789"
NOTE = f"Note: please contact {EMAIL} about the claim. Her SSN is {SSN}. Refund window is 30 days."
QUESTION = "What email and SSN are in the note? Answer briefly."


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    ap.add_argument("--device", default="auto")
    ap.add_argument("--dtype", default="auto")
    ap.add_argument("--max-new-tokens", type=int, default=64)
    ap.add_argument("--password", default=os.environ.get("PIIGUARD_PASSWORD", "qwen-demo-pass-1"))
    a = ap.parse_args()

    results: list[tuple[str, bool]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok))
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))

    with tempfile.TemporaryDirectory() as tmp:
        md = Path(tmp) / "models"
        mp.init_model("qwen-sealed", a.password, models_dir=md)          # keyring: Argon2id + wrapped DEK
        keys = unlock(a.password, mp.load_header("qwen-sealed", md))     # serve operator unlocks DEK

        llm = HFBackend(model_id=a.model_id, device=a.device, dtype=a.dtype,
                        max_new_tokens=a.max_new_tokens, temperature=0.0)
        t0 = time.time()
        llm.load()
        t_load = time.time() - t0
        print(f"loaded {a.model_id} on {llm.last_stats['device']}/{llm.last_stats['dtype']} in {t_load:.1f}s")

        req = {"modelmemory": False, "content": [{"id": "note-1", "text": NOTE}],
               "messages": [{"role": "user", "content": QUESTION}]}
        t1 = time.time()
        resp = mp.run("qwen-sealed", QUESTION, keys, models_dir=md, request=req, llm=llm)
        t_gen = time.time() - t1

        print("\n=== sealed API response (what any caller sees) ===")
        print(json.dumps(resp, indent=2))
        ans = resp["answer"]
        n_tok = len(_TOKEN_RE.findall(ans))

        check("no plaintext email in sealed answer", EMAIL not in ans)
        check("no plaintext SSN in sealed answer", SSN not in ans)
        try:
            assert_no_plaintext_pii(ans)
            check("assert_no_plaintext_pii(answer)", True)
        except AssertionError as e:
            check("assert_no_plaintext_pii(answer)", False, str(e))
        check("no plaintext PII in citations", all(EMAIL not in c["quote"] and SSN not in c["quote"]
                                                   for c in resp["citations"]))
        check("not refused / not injection-blocked", not resp["injection_blocked"]
              and "ungrounded_refused" not in resp["flags"], f"flags={resp['flags']}")

        plain = mp.decrypt("qwen-sealed", ans, a.password, models_dir=md)
        print("\n=== decrypted by password holder ===")
        print(plain)
        check("decrypt roundtrip (password holder)", _TOKEN_RE.search(plain) is None, f"{n_tok} token(s) opened")
        try:
            mp.decrypt("qwen-sealed", ans, "wrong-password-x", models_dir=md)
            check("wrong password fails closed", False)
        except Exception as e:
            check("wrong password fails closed", True, type(e).__name__)

        # Model-quality checks (informational; a small model may paraphrase/omit).
        print(f"[INFO] model returned email: {EMAIL in plain}, SSN: {SSN in plain}, sealed tokens: {n_tok}")
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        print(f"[INFO] load {t_load:.1f}s, generate+seal {t_gen:.1f}s, model chunks "
              f"{llm.last_stats.get('stream_chunks')}, prompt tokens {llm.last_stats.get('prompt_tokens')}, "
              f"peak RSS {peak:.0f} MB")

    ok = all(r for _, r in results)
    print(f"\n{'ALL PASS' if ok else 'SOME FAILED'} ({sum(r for _, r in results)}/{len(results)})")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
