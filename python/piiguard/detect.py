from __future__ import annotations
import re
from dataclasses import dataclass

@dataclass(frozen=True)
class Span:
    entity_type: str
    start: int
    end: int
    text: str

_PATTERNS = [
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("PHONE", re.compile(r"(?<!\w)(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}(?!\w)")),
    ("SSN", re.compile(r"\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b")),
    ("IP", re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b")),
]

def detect(text: str) -> list[Span]:
    found: list[Span] = []
    for etype, pat in _PATTERNS:
        for m in pat.finditer(text):
            found.append(Span(etype, m.start(), m.end(), m.group(0)))
    found.sort(key=lambda s: (s.start, -(s.end - s.start)))
    merged: list[Span] = []
    last_end = -1
    for s in found:
        if s.start < last_end:
            continue
        merged.append(s)
        last_end = s.end
    return merged
