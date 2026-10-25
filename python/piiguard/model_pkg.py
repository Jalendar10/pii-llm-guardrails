"""Ollama-style model packages: `models/<name>/` = manifest + weights + keyring.

Layout (like an Ollama Modelfile + blobs, plus a sidecar keyring):

    models/<name>/
      manifest.json      # name, digest of weights, files
      train_config.json  # copied from configs/train_config.example.json
      weights.stub       # stub weights (real impl: GGUF/safetensors) — NO password inside
      keyring.json       # PUBLIC header: salt + wrapped DEK (AES-GCM). Safe to distribute.

Anyone who pulls the package can `run` it: the serve path seals PII with the
DEK *during* token generation. To get a DEK you need the password (Argon2id →
KEK → unwrap). Honest note: AES runs in the trusted serve/keyring path, not
inside the neural weights.

Serving model (like `ollama serve`): the operator starts the server holding
the password, which unlocks the DEK in RAM so PII is sealed during generation.
Callers ("anyone can ask") only ever receive ciphertext tokens; decrypting
needs the password (or a DEK released by the key holder). `run --password`
in the CLI plays that operator role in one process.
"""
from __future__ import annotations

import hashlib, json, shutil
from pathlib import Path
from typing import Any, Iterator

from .generate import mock_llm_token_stream
from .keyring import KeyMaterial, init_from_password, rotate_password, unlock
from .pipeline import assert_no_plaintext_pii, decrypt_pii_in_text

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODELS = ROOT / "models"
DEFAULT_REGISTRY = ROOT / "registry"


def _stub_llm(prompt: str) -> Iterator[str]:
    """Stub LLM: answers simple math; answer text contains synthetic PII."""
    import re
    m = re.search(r"(-?\d+)\s*([+\-*])\s*(-?\d+)", prompt)
    if m:
        a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
        val = {"+": a + b, "-": a - b, "*": a * b}[op]
        expr = f"{a}{op}{b}={val}"
    else:
        expr = "2+2=4"
    text = f"Alice's SSN is 123-45-6789, email alice@example.com, and {expr}."
    return mock_llm_token_stream(text, chunk=1)


def init_model(name: str, password: str, *, models_dir: Path = DEFAULT_MODELS) -> Path:
    d = models_dir / name
    d.mkdir(parents=True, exist_ok=True)
    weights = d / "weights.stub"
    weights.write_bytes(b"STUB-WEIGHTS-v1 (no key material in weights)\n")
    cfg_src = ROOT / "configs" / "train_config.example.json"
    cfg = json.loads(cfg_src.read_text()) if cfg_src.exists() else {}
    cfg.setdefault("model", {})["name"] = name
    (d / "train_config.json").write_text(json.dumps(cfg, indent=2))
    km = init_from_password(password)
    hdr = km.to_public_header() | {"password_epoch": 1}
    (d / "keyring.json").write_text(json.dumps(hdr, indent=2))
    _write_manifest(d, name)
    return d


def _write_manifest(d: Path, name: str) -> None:
    digest = hashlib.sha256((d / "weights.stub").read_bytes()).hexdigest()
    (d / "manifest.json").write_text(json.dumps({
        "name": name, "weights": "weights.stub", "weights_sha256": digest,
        "keyring": "keyring.json", "train_config": "train_config.json",
    }, indent=2))


def push(name: str, *, models_dir: Path = DEFAULT_MODELS, registry: Path = DEFAULT_REGISTRY) -> Path:
    dst = registry / name
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(models_dir / name, dst)
    return dst


def pull(name: str, *, models_dir: Path = DEFAULT_MODELS, registry: Path = DEFAULT_REGISTRY) -> Path:
    src = registry / name
    if not src.exists():
        raise FileNotFoundError(f"model {name!r} not in registry {registry}")
    dst = models_dir / name
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return dst


def load_header(name: str, models_dir: Path = DEFAULT_MODELS) -> dict[str, Any]:
    return json.loads((models_dir / name / "keyring.json").read_text())


def weights_digest(name: str, models_dir: Path = DEFAULT_MODELS) -> str:
    return hashlib.sha256((models_dir / name / "weights.stub").read_bytes()).hexdigest()


def load_train_config(name: str, models_dir: Path = DEFAULT_MODELS) -> dict[str, Any]:
    p = models_dir / name / "train_config.json"
    return json.loads(p.read_text()) if p.exists() else {}


def make_llm(backend: str = "stub", prompt: str = "", *, model_id: str | None = None, **hf_kw: Any) -> Any:
    """Return a `serve.LLM` callable. backend: "stub" (default, no deps) or "hf" (transformers)."""
    if backend == "stub":
        return lambda r: _stub_llm(prompt)
    if backend == "hf":
        from .hf_backend import DEFAULT_MODEL_ID, get_backend
        return get_backend(model_id or DEFAULT_MODEL_ID, **hf_kw)
    raise ValueError(f"unknown backend {backend!r} (expected 'stub' or 'hf')")


def run(name: str, prompt: str, keys: KeyMaterial, *, models_dir: Path = DEFAULT_MODELS,
        request: dict[str, Any] | None = None, llm: Any = None) -> dict[str, Any]:
    """Serve one request through the guarded response builder (`serve.build_response`).

    A bare prompt is treated as `modelmemory=true` with no content (the stub
    answers from "memory"). Pass `request` (API shape, see configs/api_request.example.json)
    for grounded `modelmemory=false` serving.
    """
    from .serve import build_response, default_train_config

    if not (models_dir / name / "manifest.json").exists():
        raise FileNotFoundError(f"model {name!r} not found; pull it first")
    cfg = load_train_config(name, models_dir) or default_train_config()
    req = request or {"modelmemory": True, "content": [], "messages": [{"role": "user", "content": prompt}]}
    meta: dict[str, Any] = {}
    llm = llm or make_llm("stub", prompt)
    resp = build_response(req, keys, llm, train_config=cfg, meta=meta)
    assert_no_plaintext_pii(resp["answer"])
    out = {"model": name, **resp, "stream_chunks": meta.get("stream_chunks", 0)}
    if hasattr(llm, "model_id"):  # HF backend: report which weights produced the answer
        out["backend"] = {"type": "hf", "model_id": llm.model_id, **getattr(llm, "last_stats", {})}
    return out


def decrypt(name: str, text: str, password: str, *, models_dir: Path = DEFAULT_MODELS) -> str:
    keys = unlock(password, load_header(name, models_dir))  # wrong password -> InvalidTag
    return decrypt_pii_in_text(text, keys)


def rotate(name: str, old_password: str, new_password: str, *, models_dir: Path = DEFAULT_MODELS) -> dict[str, Any]:
    p = models_dir / name / "keyring.json"
    new_hdr = rotate_password(old_password, new_password, json.loads(p.read_text()))
    p.write_text(json.dumps(new_hdr, indent=2))
    return new_hdr
