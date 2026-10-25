"""Measurements reported in the IEEE paper (this box, CPU only).

1. Crypto micro-benchmarks: Argon2id unlock, seal one span, open one span.
2. Qwen3-0.6B streaming: raw stream vs stream + EncryptedGenerator, N runs,
   per-chunk timestamps for the leak-window timeline figure.
3. Stub CLI end-to-end wall time and child peak RSS.

Run from repo root:  PYTHONPATH=python python paper/ieee/scripts/measure.py
Writes paper/ieee/artifacts/measurements.json and timeline.json.
"""
from __future__ import annotations

import json, os, platform, resource, statistics as st, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ART = ROOT / "paper" / "ieee" / "artifacts"
sys.path.insert(0, str(ROOT / "python"))
os.environ.setdefault("HF_HUB_OFFLINE", "1")

from piiguard import model_pkg as mp  # noqa: E402
from piiguard.detect import detect  # noqa: E402
from piiguard.generate import EncryptedGenerator  # noqa: E402
from piiguard.hf_backend import HFBackend, build_messages  # noqa: E402
from piiguard.keyring import init_from_password, unlock  # noqa: E402
from piiguard.pipeline import decrypt_pii_in_text, encrypt_pii_in_text, grounded_pii_set  # noqa: E402

PW = "bench-pass-12345"
N_CRYPTO = 200
N_GEN = 5
MODEL_ID = os.environ.get("PIIGUARD_BENCH_MODEL", "Qwen/Qwen3-0.6B")
NOTE = ("Discharge note (synthetic): patient Maria Lopez was seen on 2026-10-02. "
        "Contact email maria.lopez@example.org. SSN 219-09-9999. Follow-up in 14 days for wound check.")
Q = "Write a short follow-up reminder for the care team. Include the patient's contact email and SSN."


def ms(xs):
    xs = [x * 1000 for x in xs]
    return {"median_ms": round(st.median(xs), 3), "min_ms": round(min(xs), 3), "max_ms": round(max(xs), 3), "n": len(xs)}


def crypto_bench() -> dict:
    km = init_from_password(PW)
    hdr = km.to_public_header()
    t_unlock = []
    for _ in range(20):
        t0 = time.perf_counter(); unlock(PW, hdr); t_unlock.append(time.perf_counter() - t0)
    t_seal, t_open, tok = [], [], None
    for _ in range(N_CRYPTO):
        t0 = time.perf_counter(); tok = encrypt_pii_in_text("219-09-9999", km).text; t_seal.append(time.perf_counter() - t0)
        t0 = time.perf_counter(); decrypt_pii_in_text(tok, km); t_open.append(time.perf_counter() - t0)
    t_det = []
    for _ in range(N_CRYPTO):
        t0 = time.perf_counter(); detect(NOTE); t_det.append(time.perf_counter() - t0)
    return {"argon2id_unlock": ms(t_unlock), "seal_ssn_span": ms(t_seal), "open_ssn_span": ms(t_open),
            "detect_note_160chars": ms(t_det), "sealed_ssn_token_len": len(tok),
            "sealed_email_token_len": len(encrypt_pii_in_text("maria.lopez@example.org", km).text)}


def gen_bench() -> tuple[dict, dict]:
    km = init_from_password(PW)
    llm = HFBackend(model_id=MODEL_ID, device="cpu", dtype="auto", max_new_tokens=96, temperature=0.0)
    t0 = time.perf_counter(); llm.load(); t_load = time.perf_counter() - t0
    req = {"modelmemory": False, "content": [{"id": "note-1", "text": NOTE}],
           "messages": [{"role": "user", "content": Q}]}
    msgs = build_messages(req)
    grounded = grounded_pii_set(NOTE, Q)
    raw_t, sealed_t, hook_t, ttfb_raw, ttfb_sealed = [], [], [], [], []
    timeline = None
    list(llm.stream_generate(msgs))  # warm-up
    for i in range(N_GEN):
        # raw stream (what a post-hoc filter would see / a plain server would flush)
        t0 = time.perf_counter(); first = None
        for c in llm.stream_generate(msgs):
            if first is None and c:
                first = time.perf_counter() - t0
        raw_t.append(time.perf_counter() - t0); ttfb_raw.append(first)
        # same request through the sealer
        gen = EncryptedGenerator(keys=km, grounded_pii=grounded)
        events, hook = [], 0.0
        t0 = time.perf_counter(); first = None
        for c in llm.stream_generate(msgs):
            ta = time.perf_counter() - t0
            h0 = time.perf_counter(); out = gen.on_token(c); hook += time.perf_counter() - h0
            te = time.perf_counter() - t0
            if out and first is None:
                first = te
            events.append({"t_arrive_s": round(ta, 4), "raw": c, "t_emit_s": round(te, 4), "emitted": out})
        h0 = time.perf_counter(); tail = gen.finish(); hook += time.perf_counter() - h0
        t_end = time.perf_counter() - t0
        events.append({"t_arrive_s": round(t_end, 4), "raw": "", "t_emit_s": round(t_end, 4), "emitted": tail})
        sealed_t.append(t_end); hook_t.append(hook); ttfb_sealed.append(first)
        if i == 0:
            timeline = {"model_id": MODEL_ID, "note": NOTE, "question": Q, "events": events,
                        "t_end_s": round(t_end, 4), "sealed_answer": gen.full_text(),
                        "decrypted": decrypt_pii_in_text(gen.full_text(), km), "n_chunks": len(events) - 1}
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    res = {"model_id": MODEL_ID, "load_s": round(t_load, 2), "runs": N_GEN, "max_new_tokens": 96,
           "prompt_tokens": llm.last_stats.get("prompt_tokens"), "stream_chunks": llm.last_stats.get("stream_chunks"),
           "raw_stream_total": ms(raw_t), "sealed_stream_total": ms(sealed_t), "sealer_hook_cpu": ms(hook_t),
           "ttfb_raw": ms(ttfb_raw), "ttfb_sealed": ms(ttfb_sealed), "peak_rss_mb": round(peak)}
    return res, timeline


def cli_bench() -> dict:
    env = dict(os.environ, PYTHONPATH=str(ROOT / "python"))
    walls = []
    with tempfile.TemporaryDirectory() as tmp:
        md = str(Path(tmp) / "m")
        subprocess.run([sys.executable, "-m", "piiguard", "--models-dir", md, "model", "init", "demo",
                        "--password", "train-time-pass-1"], check=True, capture_output=True, env=env)
        before = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        out = ""
        for _ in range(5):
            t0 = time.perf_counter()
            p = subprocess.run([sys.executable, "-m", "piiguard", "--models-dir", md, "run", "demo", "What is 2+2?",
                                "--password", "train-time-pass-1"], check=True, capture_output=True, text=True, env=env)
            walls.append(time.perf_counter() - t0); out = p.stdout
        peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024
    return {"stub_cli_run_wall": ms(walls), "stub_cli_child_peak_rss_mb": round(max(peak, before / 1024)),
            "stub_cli_stdout": out.strip()}


def main() -> int:
    import importlib.metadata, torch, transformers, cryptography
    env = {"python": platform.python_version(), "platform": platform.platform(),
           "cpu": next((l.split(":", 1)[1].strip() for l in open("/proc/cpuinfo") if l.startswith("model name")), "?"),
           "vcpus": os.cpu_count(), "torch": torch.__version__, "transformers": transformers.__version__,
           "cryptography": cryptography.__version__, "argon2_cffi": importlib.metadata.version("argon2-cffi"),
           "date": time.strftime("%Y-%m-%d %H:%M %Z")}
    out = {"env": env, "crypto": crypto_bench(), "cli": cli_bench()}
    out["generation"], tl = gen_bench()
    (ART / "measurements.json").write_text(json.dumps(out, indent=2))
    (ART / "timeline.json").write_text(json.dumps(tl, indent=2))
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
