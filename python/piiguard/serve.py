"""Trusted serve path: guardrails -> generation -> anti-hallucination -> validation.

`build_response` is the single response builder used by `piiguard run` and any
API server. Order of operations (fail closed at every step):

  1. Injection scan on user messages AND passed content (indirect injection).
     If a hit's guardrail policy is block/refuse -> fixed refusal JSON with
     `injection_blocked: true`; the model is never called.
  2. modelmemory=false without content -> refusal (ungrounded_policy).
  3. Generate through `EncryptedGenerator`:
       * model-emitted `<PII:...>` (fake ciphertext) is stripped,
       * with modelmemory=false, PII not present in content/user messages is
         NOT sealed (`hallucinated_pii_blocked`),
       * real PII is sealed with the live DEK.
  4. Post-check: every token in the answer must be one we issued AND must
     authenticate under the DEK; plaintext PII must not remain.
  5. `validate_response_shape` + `validate_grounding`; failures -> refusal.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from .detect import detect
from .generate import (
    FLAG_FAKE_TOKEN,
    FLAG_HALLUCINATED_PII,
    FLAG_UNAUTH_TOKEN,
    EncryptedGenerator,
    generate_tokens_encrypted,
)
from .injection import scan_injection
from .keyring import KeyMaterial
from .pipeline import (
    _TOKEN_RE,
    assert_no_plaintext_pii,
    encrypt_pii_in_text,
    grounded_pii_set,
    strip_unverified_tokens,
)
from .validate import validate_grounding, validate_response_shape

REFUSAL_INJECTION = "Request blocked by guardrails: possible prompt injection."
REFUSAL_UNGROUNDED = "I can't answer that from the provided content."

# injection rule -> train_config.guardrails key
_RULE_POLICY = {
    "ignore_previous": "prompt_injection",
    "disregard_system": "prompt_injection",
    "fake_system_tag": "prompt_injection",
    "jailbreak_role": "jailbreak",
    "bypass_safety": "jailbreak",
    "exfil_secrets": "exfiltration",
}
_BLOCKING = {"block", "refuse"}

_ROOT = Path(__file__).resolve().parents[2]

LLM = Callable[[dict[str, Any]], Iterable[str]]


def default_train_config() -> dict[str, Any]:
    p = _ROOT / "configs" / "train_config.example.json"
    if p.exists():
        return json.loads(p.read_text())
    return {"guardrails": {"prompt_injection": "block", "jailbreak": "refuse", "exfiltration": "block"},
            "grounding": {"default_modelmemory": False, "ungrounded_policy": "refuse"}}


def _base(**kw: Any) -> dict[str, Any]:
    r = {
        "answer": "",
        "citations": [],
        "pii_encrypted": True,  # invariant: any PII in `answer` is sealed (no plaintext)
        "injection_blocked": False,
        "grounded": False,
        "modelmemory_used": False,
        "flags": [],
    }
    r.update(kw)
    return r


def _user_texts(request: dict[str, Any]) -> list[str]:
    return [str(m.get("content", "")) for m in request.get("messages", []) if m.get("role", "user") == "user"]


def _content_docs(request: dict[str, Any]) -> list[dict[str, str]]:
    return [{"id": str(d.get("id", f"doc-{i}")), "text": str(d.get("text", ""))}
            for i, d in enumerate(request.get("content") or [])]


def check_injection(request: dict[str, Any], train_config: dict[str, Any]) -> list[str]:
    """Return blocking rule names (empty = allowed). Scans user msgs + content."""
    guard = train_config.get("guardrails", {})
    blocking: list[str] = []
    for text in _user_texts(request) + [d["text"] for d in _content_docs(request)]:
        for hit in scan_injection(text):
            policy = guard.get(_RULE_POLICY.get(hit.rule, "prompt_injection"), "block")
            if policy in _BLOCKING and hit.rule not in blocking:
                blocking.append(hit.rule)
    return blocking


_WORD = re.compile(r"[a-z0-9]+")
_STOP = {"the", "a", "an", "is", "are", "of", "to", "and", "or", "for", "in", "on", "at", "it", "be", "your", "you"}


def _mask(text: str) -> str:
    text = _TOKEN_RE.sub(lambda m: f" pii{m.group('type').lower()} ", text)
    out, last = [], 0
    for s in detect(text):
        out.append(text[last:s.start]); out.append(f" pii{s.entity_type.lower()} "); last = s.end
    out.append(text[last:])
    return "".join(out)


def _words(text: str) -> set[str]:
    return {w for w in _WORD.findall(_mask(text).lower()) if w not in _STOP}


def ground_citations(answer: str, docs: list[dict[str, str]], keys: KeyMaterial, tenant: str) -> list[dict[str, str]]:
    """Cite content sentences that share >=50% of their content words with the answer.

    Works on the sealed answer (PII tokens compare by type only), so no answer
    plaintext is needed. Quotes are themselves PII-sealed.
    """
    aw = _words(answer)
    cites: list[dict[str, str]] = []
    for d in docs:
        for sent in re.split(r"(?<=[.!?])\s+", d["text"]):
            sw = _words(sent)
            if sw and len(sw & aw) / len(sw) >= 0.5:
                cites.append({"source_id": d["id"], "quote": encrypt_pii_in_text(sent.strip(), keys, tenant=tenant).text})
    return cites


def build_response(
    request: dict[str, Any],
    keys: KeyMaterial,
    llm: LLM,
    *,
    train_config: dict[str, Any] | None = None,
    tenant: str = "default",
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = train_config or default_train_config()
    grounding_cfg = cfg.get("grounding", {})
    modelmemory = bool(request.get("modelmemory", grounding_cfg.get("default_modelmemory", False)))
    docs = _content_docs(request)
    content_passed = any(d["text"].strip() for d in docs)

    # 1. guardrails before any generation
    rules = check_injection(request, cfg)
    if rules:
        return _base(answer=REFUSAL_INJECTION, injection_blocked=True, modelmemory_used=modelmemory,
                     flags=["injection_blocked"] + [f"injection_rule:{r}" for r in rules])

    # 2. ungrounded request
    if not modelmemory and not content_passed:
        return _base(answer=REFUSAL_UNGROUNDED, flags=["ungrounded_refused", "no_content"])

    # 3. generation through the trusted sealer
    grounded = None if modelmemory else grounded_pii_set(*[d["text"] for d in docs], *_user_texts(request))
    gen = EncryptedGenerator(keys=keys, tenant=tenant, grounded_pii=grounded)
    chunks = list(generate_tokens_encrypted(llm(request), keys, generator=gen))
    answer = "".join(chunks)
    flags = set(gen.flags)

    if FLAG_HALLUCINATED_PII in flags and grounding_cfg.get("ungrounded_pii_policy", "drop") == "refuse":
        return _base(answer=REFUSAL_UNGROUNDED, modelmemory_used=modelmemory,
                     flags=sorted(flags | {"ungrounded_refused"}))

    # 4. only tokens we sealed with the live DEK may leave the server
    answer, n_bad = strip_unverified_tokens(answer, keys, tenant=tenant, issued=gen.issued_tokens)
    if n_bad:
        flags.add(FLAG_UNAUTH_TOKEN)
    assert_no_plaintext_pii(answer)

    citations = ground_citations(answer, docs, keys, tenant) if content_passed else []
    resp = _base(
        answer=answer,
        citations=citations,
        grounded=bool(citations),
        modelmemory_used=modelmemory,
        flags=sorted(flags),
    )
    if meta is not None:
        meta["stream_chunks"] = len(chunks)

    # 5. validate; fail closed to a refusal
    errors = validate_response_shape(resp) + validate_grounding(
        modelmemory=modelmemory, content_passed=content_passed, response=resp)
    if errors:
        policy = grounding_cfg.get("ungrounded_policy", "refuse")
        if policy == "refuse" or validate_response_shape(resp):
            return _base(answer=REFUSAL_UNGROUNDED, modelmemory_used=modelmemory,
                         flags=sorted(flags | {"validation_failed", "ungrounded_refused"})
                         + [f"validation:{e}" for e in errors])
        resp["flags"] = sorted(flags) + [f"validation:{e}" for e in errors]
    return resp
