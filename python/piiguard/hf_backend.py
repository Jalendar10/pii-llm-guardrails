"""Hugging Face causal-LM backend (Qwen3 by default) for the trusted serve path.

`HFBackend` is an `LLM` callable (`request -> Iterable[str]`) for
`serve.build_response`. It streams decoded text chunks from `model.generate`
via `TextIteratorStreamer` running in a worker thread, so every chunk passes
through `EncryptedGenerator.on_token` *while the model is still generating*:
plaintext PII is sealed before it leaves the serve process. Injection
checks, grounding, fake-token stripping and DEK verification are unchanged —
this module only replaces the stub token source.

Default model is `Qwen/Qwen3-8B` (needs a GPU or Apple MPS with ~17 GB free
for bf16/fp16). For CPU smoke tests use `--model-id Qwen/Qwen3-0.6B`.

Heavy deps (torch, transformers) are imported lazily so the stub path and the
stub test-suite never need them.
"""
from __future__ import annotations

import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

DEFAULT_MODEL_ID = "Qwen/Qwen3-8B"
SMOKE_MODEL_ID = "Qwen/Qwen3-0.6B"
DEFAULT_MAX_NEW_TOKENS = 64

SYSTEM_PROMPT_GROUNDED = (
    "You are a careful assistant. Answer ONLY from the provided content. "
    "If the content does not contain the answer, say you cannot answer from the provided content. "
    "Write values exactly as they appear in the content. Never output tags like <PII:...>. "
    "Be brief."
)
SYSTEM_PROMPT_MEMORY = (
    "You are a careful assistant. Answer briefly. Never output tags like <PII:...>."
)


class HFBackendError(RuntimeError):
    """Model/tokenizer could not be loaded (missing deps, gated repo, network, OOM)."""


def pick_device(pref: str = "auto") -> str:
    import torch

    if pref != "auto":
        return pref
    if torch.cuda.is_available():
        return "cuda"
    mps = getattr(torch.backends, "mps", None)
    if mps is not None and mps.is_available():
        return "mps"
    return "cpu"


def pick_dtype(device: str, pref: str = "auto") -> Any:
    import torch

    table = {"float32": torch.float32, "fp32": torch.float32, "bfloat16": torch.bfloat16,
             "bf16": torch.bfloat16, "float16": torch.float16, "fp16": torch.float16}
    if pref != "auto":
        return table[pref]
    if device == "cuda":
        return torch.bfloat16
    if device == "mps":
        return torch.float16  # bf16 on MPS needs macOS 14+; fp16 is the safe default
    return torch.bfloat16  # CPU: halves RAM vs fp32; use --dtype float32 if your CPU lacks bf16


def build_messages(request: dict[str, Any], *, system_prompt: str | None = None) -> list[dict[str, str]]:
    """API request -> chat messages. Content docs go in the system turn (grounding)."""
    docs = [d for d in (request.get("content") or []) if str(d.get("text", "")).strip()]
    modelmemory = bool(request.get("modelmemory", False))
    sys_txt = system_prompt or (SYSTEM_PROMPT_MEMORY if modelmemory and not docs else SYSTEM_PROMPT_GROUNDED)
    if docs:
        blocks = "\n\n".join(f"[{d.get('id', f'doc-{i}')}]\n{d.get('text', '')}" for i, d in enumerate(docs))
        sys_txt = f"{sys_txt}\n\n### Content\n{blocks}"
    msgs = [{"role": "system", "content": sys_txt}]
    for m in request.get("messages") or []:
        role = m.get("role", "user")
        if role in ("user", "assistant"):
            msgs.append({"role": role, "content": str(m.get("content", ""))})
    return msgs


class _ThinkStripper:
    """Drop `<think>...</think>` blocks from a text stream (only used if thinking is on)."""

    def __init__(self) -> None:
        self._buf, self._in = "", False

    def feed(self, s: str, final: bool = False) -> str:
        self._buf += s
        out: list[str] = []
        while True:
            tag = "</think>" if self._in else "<think>"
            i = self._buf.find(tag)
            if i >= 0:
                if not self._in:
                    out.append(self._buf[:i])
                self._buf, self._in = self._buf[i + len(tag):], not self._in
                continue
            if final:
                if not self._in:
                    out.append(self._buf)
                self._buf = ""
                break
            # keep a possible partial tag at the tail
            keep = next((k for k in range(min(len(tag) - 1, len(self._buf)), 0, -1)
                         if tag.startswith(self._buf[-k:])), 0)
            emit, self._buf = self._buf[: len(self._buf) - keep], self._buf[len(self._buf) - keep:]
            if not self._in:
                out.append(emit)
            break
        return "".join(out)


@dataclass
class HFBackend:
    model_id: str = DEFAULT_MODEL_ID
    device: str = "auto"
    dtype: str = "auto"
    max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS
    temperature: float | None = None  # None/0 -> greedy (deterministic smoke tests)
    enable_thinking: bool = False
    system_prompt: str | None = None
    _tok: Any = field(default=None, init=False, repr=False)
    _model: Any = field(default=None, init=False, repr=False)
    last_stats: dict[str, Any] = field(default_factory=dict, init=False)

    # -- loading -------------------------------------------------------------
    def load(self) -> "HFBackend":
        if self._model is not None:
            return self
        try:
            import torch  # noqa: F401
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as e:  # pragma: no cover - env dependent
            raise HFBackendError(
                "torch/transformers not installed: pip install torch --index-url "
                "https://download.pytorch.org/whl/cpu && pip install 'transformers>=4.51' accelerate"
            ) from e
        dev = pick_device(self.device)
        dt = pick_dtype(dev, self.dtype)
        try:
            self._tok = AutoTokenizer.from_pretrained(self.model_id)
            self._model = AutoModelForCausalLM.from_pretrained(self.model_id, dtype=dt, low_cpu_mem_usage=True)
            self._model.to(dev).eval()
        except Exception as e:
            raise HFBackendError(f"failed to load {self.model_id!r} on {dev}/{dt}: {type(e).__name__}: {e}") from e
        self.device, self.last_stats = dev, {"device": dev, "dtype": str(dt).replace("torch.", "")}
        return self

    # -- generation ----------------------------------------------------------
    def stream_generate(self, messages: list[dict[str, str]], max_new_tokens: int | None = None,
                        temperature: float | None = None) -> Iterator[str]:
        """Yield decoded text chunks while `model.generate` runs in a worker thread."""
        import torch
        from transformers import StoppingCriteria, StoppingCriteriaList, TextIteratorStreamer

        self.load()
        tok, model = self._tok, self._model
        prompt = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True,
                                         enable_thinking=self.enable_thinking)
        inputs = tok(prompt, return_tensors="pt").to(model.device)
        streamer = TextIteratorStreamer(tok, skip_prompt=True, skip_special_tokens=True, timeout=600.0)
        cancel = threading.Event()

        class _Cancel(StoppingCriteria):
            def __call__(self, input_ids, scores, **kw):  # type: ignore[override]
                return cancel.is_set()

        temp = self.temperature if temperature is None else temperature
        kw: dict[str, Any] = dict(**inputs, streamer=streamer,
                                  max_new_tokens=int(max_new_tokens or self.max_new_tokens),
                                  stopping_criteria=StoppingCriteriaList([_Cancel()]),
                                  pad_token_id=tok.pad_token_id or tok.eos_token_id)
        if temp and temp > 0:
            kw.update(do_sample=True, temperature=float(temp), top_p=0.8, top_k=20)
        else:
            kw.update(do_sample=False, temperature=None, top_p=None, top_k=None)
        err: list[BaseException] = []

        def _run() -> None:
            try:
                with torch.inference_mode():
                    model.generate(**kw)
            except BaseException as e:  # surfaced to the consumer below
                err.append(e)
                streamer.end()

        th = threading.Thread(target=_run, name="hf-generate", daemon=True)
        th.start()
        strip = _ThinkStripper() if self.enable_thinking else None
        n = 0
        try:
            for chunk in streamer:
                n += 1
                piece = strip.feed(chunk) if strip else chunk
                if piece:
                    yield piece
            if strip:
                tail = strip.feed("", final=True)
                if tail:
                    yield tail
        finally:
            cancel.set()  # consumer stopped early (e.g. fail-closed) -> stop generating
            th.join()
            self.last_stats.update(prompt_tokens=int(inputs["input_ids"].shape[-1]), stream_chunks=n)
        if err:
            raise err[0]

    def __call__(self, request: dict[str, Any]) -> Iterator[str]:
        """`serve.LLM` interface."""
        cap = self.max_new_tokens
        if request.get("max_tokens"):
            cap = min(cap, int(request["max_tokens"]))
        # backend temperature (CLI/operator) wins; otherwise honour the request's
        temp = self.temperature if self.temperature is not None else request.get("temperature")
        return self.stream_generate(build_messages(request, system_prompt=self.system_prompt),
                                    max_new_tokens=cap, temperature=temp)


_CACHE: dict[tuple, HFBackend] = {}


def get_backend(model_id: str = DEFAULT_MODEL_ID, **kw: Any) -> HFBackend:
    """Process-wide cache so a server loads weights once."""
    key = (model_id, tuple(sorted(kw.items())))
    if key not in _CACHE:
        _CACHE[key] = HFBackend(model_id=model_id, **kw)
    return _CACHE[key]
