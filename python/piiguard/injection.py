"""Prompt-injection / jailbreak heuristics (train-time list + runtime scan)."""

from __future__ import annotations

import re
from dataclasses import dataclass

_PATTERNS = [
    (r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", "ignore_previous"),
    (r"disregard\s+(your\s+)?(system|developer)\s+(prompt|instructions)", "disregard_system"),
    (r"you\s+are\s+now\s+(dan|jailbroken|unrestricted)", "jailbreak_role"),
    (r"reveal\s+(your\s+)?(system\s+prompt|hidden\s+instructions|password|salt|dek|key)", "exfil_secrets"),
    (r"do\s+not\s+follow\s+your\s+(safety|guardrail)", "bypass_safety"),
    (r"<\s*/?\s*system\s*>", "fake_system_tag"),
]


@dataclass
class InjectionHit:
    rule: str
    span: str


def scan_injection(text: str) -> list[InjectionHit]:
    hits: list[InjectionHit] = []
    lower = text.lower()
    for pat, rule in _PATTERNS:
        for m in re.finditer(pat, lower, flags=re.I):
            hits.append(InjectionHit(rule=rule, span=text[m.start() : m.end()]))
    return hits


def is_blocked(text: str) -> bool:
    return bool(scan_injection(text))
