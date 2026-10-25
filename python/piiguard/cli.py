"""piiguard CLI — Ollama-style: model init/push/pull/list, run, decrypt, rotate."""
from __future__ import annotations

import argparse, json, sys
from pathlib import Path

from . import model_pkg as mp
from .keyring import unlock


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="piiguard")
    ap.add_argument("--models-dir", type=Path, default=mp.DEFAULT_MODELS)
    ap.add_argument("--registry", type=Path, default=mp.DEFAULT_REGISTRY)
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("model").add_subparsers(dest="mcmd", required=True)
    i = m.add_parser("init"); i.add_argument("name"); i.add_argument("--password", required=True)
    for n in ("push", "pull"):
        x = m.add_parser(n); x.add_argument("name")
    m.add_parser("list")
    r = sub.add_parser("run"); r.add_argument("name"); r.add_argument("prompt")
    r.add_argument("--password", required=True, help="operator/serve-side key holder")
    r.add_argument("--request", type=Path, help="API request JSON (content/messages/modelmemory)")
    r.add_argument("--content", action="append", default=[],
                   help="grounding content text (repeatable); implies modelmemory=false")
    r.add_argument("--backend", choices=("stub", "hf"), default="stub", help="token source (default: stub)")
    r.add_argument("--model-id", default=None, help="HF model id for --backend hf (default: Qwen/Qwen3-8B)")
    r.add_argument("--device", default="auto", help="hf: auto|cpu|cuda|mps")
    r.add_argument("--dtype", default="auto", help="hf: auto|float32|bfloat16|float16")
    r.add_argument("--max-new-tokens", type=int, default=64, help="hf: generation cap")
    r.add_argument("--temperature", type=float, default=None, help="hf: 0/None = greedy")
    r.add_argument("--enable-thinking", action="store_true", help="hf: Qwen3 thinking mode (stripped from output)")
    d = sub.add_parser("decrypt"); d.add_argument("name"); d.add_argument("text")
    d.add_argument("--password", required=True)
    ro = sub.add_parser("rotate"); ro.add_argument("name")
    ro.add_argument("--old-password", required=True); ro.add_argument("--new-password", required=True)
    a = ap.parse_args(argv)
    md, reg = a.models_dir, a.registry
    try:
        if a.cmd == "model":
            if a.mcmd == "init":
                print(mp.init_model(a.name, a.password, models_dir=md))
            elif a.mcmd == "push":
                print(mp.push(a.name, models_dir=md, registry=reg))
            elif a.mcmd == "pull":
                print(mp.pull(a.name, models_dir=md, registry=reg))
            else:
                for p in sorted(md.glob("*/manifest.json")):
                    print(p.parent.name)
        elif a.cmd == "run":
            keys = unlock(a.password, mp.load_header(a.name, md))
            req = json.loads(a.request.read_text()) if a.request else None
            if a.content:
                req = req or {"modelmemory": False}
                req.setdefault("content", []).extend(
                    {"id": f"cli-{i}", "text": t} for i, t in enumerate(a.content))
                req["modelmemory"] = False
            if req is not None:
                req.setdefault("messages", []).append({"role": "user", "content": a.prompt})
            llm = mp.make_llm(a.backend, a.prompt, model_id=a.model_id, device=a.device, dtype=a.dtype,
                              max_new_tokens=a.max_new_tokens, temperature=a.temperature,
                              enable_thinking=a.enable_thinking) if a.backend == "hf" else None
            print(json.dumps(mp.run(a.name, a.prompt, keys, models_dir=md, request=req, llm=llm)))
        elif a.cmd == "decrypt":
            print(mp.decrypt(a.name, a.text, a.password, models_dir=md))
        elif a.cmd == "rotate":
            h = mp.rotate(a.name, a.old_password, a.new_password, models_dir=md)
            print(json.dumps({"rotated": True, "password_epoch": h["password_epoch"]}))
    except Exception as e:  # fail closed, no plaintext
        from .hf_backend import HFBackendError
        if isinstance(e, HFBackendError):  # load errors carry no user data; show why
            print(f"ERROR (fail closed): {e}", file=sys.stderr)
            return 2
        print(f"ERROR (fail closed): {type(e).__name__}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
