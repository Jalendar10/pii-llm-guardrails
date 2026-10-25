from __future__ import annotations
import base64, json, re
from dataclasses import dataclass
from . import open as crypto_open, seal
from .detect import Span, detect
from .keyring import KeyMaterial

_TOKEN_RE = re.compile(r"<PII:(?P<type>[A-Z_]+):(?P<b64>[A-Za-z0-9_\-=]+)>")
# Anything that *looks* like a PII token, including malformed / case / spacing
# variants a model might hallucinate. Used for verification, not decryption.
_LOOSE_TOKEN_RE = re.compile(r"<\s*PII\s*:[^<>]{0,8192}>", re.I)
_LOOSE_OPEN_RE = re.compile(r"<\s*PII\s*:", re.I)

FAKE_TOKEN_PLACEHOLDER = "[REDACTED:UNVERIFIED_TOKEN]"


def normalize_pii(entity_type: str, text: str) -> tuple[str, str]:
    """Canonical form used to compare model-emitted PII with grounding sources."""
    t = text.strip()
    if entity_type == "EMAIL":
        t = t.lower()
    elif entity_type in ("PHONE", "SSN", "CREDIT_CARD"):
        t = re.sub(r"\D", "", t)
        if entity_type == "PHONE" and len(t) == 11 and t.startswith("1"):
            t = t[1:]
    return entity_type, t


def grounded_pii_set(*sources: str) -> frozenset[tuple[str, str]]:
    """All PII values present in trusted grounding sources (content + user msgs)."""
    return frozenset(normalize_pii(s.entity_type, s.text) for src in sources for s in detect(src or ""))

@dataclass
class EncryptResult:
    text: str
    spans_encrypted: int
    plaintext_remaining: list[str]

def _pack_blob(version: int, nonce: bytes, ciphertext: bytes, etype: str) -> str:
    payload = {
        "v": version,
        "n": base64.urlsafe_b64encode(nonce).decode(),
        "c": base64.urlsafe_b64encode(ciphertext).decode(),
        "t": etype,
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")

def _unpack_blob(b64: str):
    pad = "=" * (-len(b64) % 4)
    payload = json.loads(base64.urlsafe_b64decode(b64 + pad).decode())
    return int(payload["v"]), base64.urlsafe_b64decode(payload["n"]), base64.urlsafe_b64decode(payload["c"]), str(payload["t"])

def _detect_outside_tokens(text: str) -> list[Span]:
    parts, last = [], 0
    for m in _TOKEN_RE.finditer(text):
        parts.append(text[last:m.start()])
        parts.append(" " * (m.end() - m.start()))
        last = m.end()
    parts.append(text[last:])
    return detect("".join(parts))

def encrypt_pii_in_text(text: str, keys: KeyMaterial, *, tenant: str = "default") -> EncryptResult:
    spans = detect(text)
    if not spans:
        return EncryptResult(text, 0, [])
    out, cursor = [], 0
    for span in spans:
        out.append(text[cursor:span.start])
        aad = f"{tenant}|{span.entity_type}|{keys.key_version}".encode()
        version, nonce, ct = seal(keys.dek, span.text.encode(), aad)
        out.append(f"<PII:{span.entity_type}:{_pack_blob(version, nonce, ct, span.entity_type)}>")
        cursor = span.end
    out.append(text[cursor:])
    result = "".join(out)
    return EncryptResult(result, len(spans), [s.text for s in _detect_outside_tokens(result)])

def decrypt_pii_in_text(text: str, keys: KeyMaterial, *, tenant: str = "default") -> str:
    def repl(m: re.Match[str]) -> str:
        etype = m.group("type")
        version, nonce, ct, blob_type = _unpack_blob(m.group("b64"))
        if blob_type != etype:
            raise ValueError("token type mismatch")
        aad = f"{tenant}|{etype}|{keys.key_version}".encode()
        return crypto_open(keys.dek, version, nonce, ct, aad).decode()
    return _TOKEN_RE.sub(repl, text)

def assert_no_plaintext_pii(text: str) -> None:
    leftover = _detect_outside_tokens(text)
    if leftover:
        raise AssertionError("plaintext PII leaked: " + ", ".join(repr(s.text) for s in leftover))


def verify_pii_tokens(
    text: str,
    keys: KeyMaterial,
    *,
    tenant: str = "default",
    issued: set[str] | None = None,
) -> list[str]:
    """Return every token-looking substring that is NOT a genuine sealed token.

    Genuine = strict format, GCM-authenticates under `keys.dek` with our AAD,
    blob type matches, and (if `issued` given) was produced by this serve path.
    Also reports any dangling `<PII:` opener. Never returns plaintext.
    """
    bad: list[str] = []
    good_spans: list[tuple[int, int]] = []
    for m in _LOOSE_TOKEN_RE.finditer(text):
        tok = m.group(0)
        ok = False
        sm = _TOKEN_RE.fullmatch(tok)
        if sm and (issued is None or tok in issued):
            try:
                version, nonce, ct, blob_type = _unpack_blob(sm.group("b64"))
                if blob_type == sm.group("type"):
                    aad = f"{tenant}|{blob_type}|{keys.key_version}".encode()
                    crypto_open(keys.dek, version, nonce, ct, aad)
                    ok = True
            except Exception:
                ok = False
        if ok:
            good_spans.append((m.start(), m.end()))
        else:
            bad.append(tok)
    for m in _LOOSE_OPEN_RE.finditer(text):
        if not any(a == m.start() for a, _ in good_spans) and not any(
            tm.start() == m.start() for tm in _LOOSE_TOKEN_RE.finditer(text)
        ):
            bad.append(m.group(0))
    return bad


def strip_unverified_tokens(
    text: str,
    keys: KeyMaterial,
    *,
    tenant: str = "default",
    issued: set[str] | None = None,
) -> tuple[str, int]:
    """Replace every non-genuine token (see verify_pii_tokens) with a placeholder."""
    bad = set(verify_pii_tokens(text, keys, tenant=tenant, issued=issued))
    if not bad:
        return text, 0
    count = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal count
        if m.group(0) in bad:
            count += 1
            return FAKE_TOKEN_PLACEHOLDER
        return m.group(0)

    text = _LOOSE_TOKEN_RE.sub(repl, text)
    # dangling openers that never closed
    parts, last = [], 0
    for m in _LOOSE_OPEN_RE.finditer(text):
        if _LOOSE_TOKEN_RE.match(text, m.start()) and _LOOSE_TOKEN_RE.match(text, m.start()).group(0) not in bad:
            continue
        parts.append(text[last:m.start()]); parts.append(FAKE_TOKEN_PLACEHOLDER); last = m.end(); count += 1
    parts.append(text[last:])
    return "".join(parts), count
