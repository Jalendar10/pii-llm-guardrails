"""Encrypt PII *during* LLM token generation — inside the generate loop.

Each new token goes through `EncryptedGenerator.on_token`. Plaintext PII
characters are held in a buffer and never emitted. When a PII span
completes, the sealed token is emitted instead — still during generation,
before the next tokens are released to the API client.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

from .detect import Span, detect
from .keyring import KeyMaterial
from .pipeline import (
    FAKE_TOKEN_PLACEHOLDER,
    assert_no_plaintext_pii,
    encrypt_pii_in_text,
    normalize_pii,
    verify_pii_tokens,
)

# ---------------------------------------------------------------------------
# Anti-hallucination rule: the neural model MUST NEVER produce ciphertext.
# Anything the model emits that looks like a `<PII:...>` token is fake (it was
# not sealed with the live DEK) and is stripped *before* it reaches the
# detect/seal buffer. Only `_seal_span` below creates real tokens.
# ---------------------------------------------------------------------------
_FAKE_OPEN_RE = re.compile(r"<\s*PII\s*:", re.I)
# A buffer tail that could still grow into "<PII:" (e.g. "<", "<P", "< pi", "<PII ").
_FAKE_PREFIX_RE = re.compile(r"<\s*(?:P(?:I(?:I\s*)?)?)?$", re.I)

FLAG_FAKE_TOKEN = "fake_pii_token_stripped"
FLAG_HALLUCINATED_PII = "hallucinated_pii_blocked"
FLAG_UNAUTH_TOKEN = "unauthenticated_pii_token_stripped"


def ungrounded_placeholder(entity_type: str) -> str:
    return f"[REDACTED:UNGROUNDED_{entity_type}]"


def _last_word_start(text: str) -> int:
    m = re.search(r"[^\s,;:!?\[\]\(\)\{\}\"']+$", text)
    return m.start() if m else len(text)


def _hold_from(text: str) -> int | None:
    """Index where we must stop emitting — start of a possible incomplete PII.

    Returns None if the whole text is safe to emit as plaintext (no open candidate).
    """
    if not text:
        return None

    # Incomplete EMAIL (local@domain without TLD, or local-part that may gain @)
    last_start = _last_word_start(text)
    last = text[last_start:]
    if "@" in last:
        if not re.search(r"@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", last):
            return last_start
    else:
        # local-part-ish: hold so we don't leak "jalendarreddy97" before "@gmail.com"
        if re.fullmatch(r"[A-Za-z0-9._%+\-]{2,}", last):
            return last_start

    # Incomplete SSN: ddd, ddd-, ddd-dd, ddd-dd-
    if re.search(r"(?:^|[^\d])(\d{3}(-?\d{0,2}(-?\d{0,4})?)?)$", text):
        frag = re.search(r"(\d{3}(?:-\d{0,2}(?:-\d{0,4})?)?)$", text)
        if frag and not re.fullmatch(r"\d{3}-\d{2}-\d{4}", frag.group(1)):
            # only hold if it looks like SSN in progress (has hyphen started or exactly 3 digits after boundary)
            g = frag.group(1)
            if "-" in g or len(g) == 3:
                return text.rfind(g)

    # Incomplete phone: accumulating digits
    if re.search(r"[\d\-+().\s]{6,}$", text) and not detect(text[-20:]):
        # if many digits without a completed phone/ssn match, hold digit run
        m = re.search(r"([\d\-+().\s]{6,})$", text)
        if m and not any(s.end == len(text) for s in detect(text)):
            # completed phones are caught by detect; if detect empty on tail, hold
            if re.search(r"\d", m.group(1)):
                return m.start(1)

    return None


def _seal_span(span: Span, keys: KeyMaterial, tenant: str) -> str:
    # Reuse pipeline packing via encrypt on just the span in isolation with markers
    # Simpler: encrypt a one-span string
    piece = encrypt_pii_in_text(span.text, keys, tenant=tenant)
    # encrypt_pii_in_text returns only the token if text is pure PII
    return piece.text


@dataclass
class EncryptedGenerator:
    """Hook for the model generate loop: `for tok in model: yield gen.on_token(tok)`.

    Pipeline per model token:
      1. `_sanitize`: strip any model-emitted `<PII:...>` (fake ciphertext).
      2. buffer + detect plaintext PII.
      3. grounding gate: if `grounded_pii` is set, a detected span whose
         normalized value is not in it is NOT sealed (replaced + flagged).
      4. `_seal_span` with the live DEK; the token is recorded in `issued_tokens`.
    `finish()` re-verifies that every token in the output was issued here and
    authenticates under the DEK (AES-GCM).
    """

    keys: KeyMaterial
    tenant: str = "default"
    # Normalized PII values (see pipeline.normalize_pii) that may be sealed.
    # None = no grounding gate (modelmemory=true behaviour).
    grounded_pii: frozenset[tuple[str, str]] | None = None
    _buf: str = field(default="", init=False)
    _plain_emitted: int = field(default=0, init=False)
    _out: str = field(default="", init=False)
    _pending: str = field(default="", init=False)  # raw model text not yet sanitized
    _in_fake: bool = field(default=False, init=False)
    issued_tokens: set[str] = field(default_factory=set, init=False)
    flags: set[str] = field(default_factory=set, init=False)
    blocked_counts: dict[str, int] = field(default_factory=dict, init=False)

    def on_token(self, token: str) -> str:
        if not token:
            return ""
        self._buf += self._sanitize(token, final=False)
        return self._advance(final=False)

    def finish(self) -> str:
        self._buf += self._sanitize("", final=True)
        piece = self._advance(final=True)
        assert_no_plaintext_pii(self._out)
        bad = verify_pii_tokens(self._out, self.keys, tenant=self.tenant, issued=self.issued_tokens)
        if bad:
            # Defense in depth: should be unreachable because fakes are stripped
            # before buffering. Fail closed on the full text.
            self.flags.add(FLAG_UNAUTH_TOKEN)
            raise AssertionError(f"{len(bad)} unauthenticated PII token(s) in generator output")
        return piece

    def full_text(self) -> str:
        return self._out

    # -- step 1: fake-ciphertext stripping ---------------------------------
    def _sanitize(self, token: str, *, final: bool) -> str:
        """Return model text that is safe to buffer; never contains `<PII:`."""
        self._pending += token
        out: list[str] = []
        while self._pending:
            if self._in_fake:
                end = self._pending.find(">")
                if end < 0:
                    self._pending = ""  # drop fake blob body; keep waiting for '>'
                    break
                self._pending = self._pending[end + 1 :]
                self._in_fake = False
                continue
            m = _FAKE_OPEN_RE.search(self._pending)
            if m:
                out.append(self._pending[: m.start()])
                out.append(FAKE_TOKEN_PLACEHOLDER)
                self.flags.add(FLAG_FAKE_TOKEN)
                self._pending = self._pending[m.end() :]
                self._in_fake = True
                continue
            if final:
                out.append(self._pending)  # e.g. a lone "<P" is just text
                self._pending = ""
                break
            hold = _FAKE_PREFIX_RE.search(self._pending)
            cut = hold.start() if hold else len(self._pending)
            out.append(self._pending[:cut])
            self._pending = self._pending[cut:]
            break
        if final:
            self._pending = ""
            self._in_fake = False  # unterminated fake token: already dropped
        return "".join(out)

    # -- step 3/4: grounding gate + seal -----------------------------------
    def _emit_span(self, span: Span) -> str:
        if self.grounded_pii is not None and normalize_pii(span.entity_type, span.text) not in self.grounded_pii:
            # Plaintext PII the model invented (not in content / user message):
            # never seal it — a sealed hallucination would look authoritative.
            self.flags.add(FLAG_HALLUCINATED_PII)
            self.blocked_counts[span.entity_type] = self.blocked_counts.get(span.entity_type, 0) + 1
            return ungrounded_placeholder(span.entity_type)
        tok = _seal_span(span, self.keys, self.tenant)
        self.issued_tokens.add(tok)
        return tok

    def _safe_limit(self) -> int:
        """Largest prefix of the buffer that can never become part of a future PII span."""
        buf = self._buf
        safe = len(buf)
        # Hold the trailing word (any length) — it may grow into an email/SSN/IP.
        safe = min(safe, _last_word_start(buf))
        # Hold a trailing run of phone-ish chars (e.g. "or (", "555 12").
        m = re.search(r"[\d\-+().\s]+$", buf)
        if m:
            safe = min(safe, m.start())
        h = _hold_from(buf)
        if h is not None:
            safe = min(safe, h)
        # A detected span touching the buffer end may still extend (".co" -> ".com").
        changed = True
        while changed:
            changed = False
            for sp in detect(buf):
                if sp.start < safe and (sp.end > safe or sp.end == len(buf)):
                    safe = sp.start
                    changed = True
        return max(safe, self._plain_emitted)

    def _advance(self, *, final: bool) -> str:
        limit = len(self._buf) if final else self._safe_limit()
        newly: list[str] = []
        cur = self._plain_emitted
        for span in detect(self._buf):
            if span.end <= cur:
                continue
            if span.start < cur:
                # Would mean plaintext of this span was already released: fail closed.
                raise AssertionError("PII span overlaps already-emitted output")
            if span.end > limit:
                break
            newly.append(self._buf[cur:span.start])
            newly.append(self._emit_span(span))
            cur = span.end
        if limit > cur:
            # Only plaintext remains in [cur, limit) (spans beyond limit start at/after it).
            nxt = [sp.start for sp in detect(self._buf) if sp.start >= cur]
            stop = min([limit] + nxt)
            newly.append(self._buf[cur:stop])
            cur = stop
        self._plain_emitted = cur
        piece = "".join(newly)
        self._out += piece
        return piece


def generate_tokens_encrypted(
    token_stream: Iterable[str],
    keys: KeyMaterial,
    *,
    tenant: str = "default",
    grounded_pii: frozenset[tuple[str, str]] | None = None,
    generator: EncryptedGenerator | None = None,
) -> Iterator[str]:
    gen = generator or EncryptedGenerator(keys=keys, tenant=tenant, grounded_pii=grounded_pii)
    for tok in token_stream:
        piece = gen.on_token(tok)
        if piece:
            yield piece
    final = gen.finish()
    if final:
        yield final


def mock_llm_token_stream(text: str, *, chunk: int = 1) -> Iterator[str]:
    for i in range(0, len(text), chunk):
        yield text[i : i + chunk]
