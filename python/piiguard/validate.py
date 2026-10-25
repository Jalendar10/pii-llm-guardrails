"""Output validation: schema + grounding + modelmemory policy."""

from __future__ import annotations

from typing import Any


REQUIRED_KEYS = (
    "answer",
    "citations",
    "pii_encrypted",
    "injection_blocked",
    "grounded",
    "modelmemory_used",
)


def validate_response_shape(obj: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for k in REQUIRED_KEYS:
        if k not in obj:
            errors.append(f"missing field: {k}")
    if "citations" in obj and not isinstance(obj["citations"], list):
        errors.append("citations must be a list")
    if "pii_encrypted" in obj and obj["pii_encrypted"] is not True:
        errors.append("pii_encrypted must be true")
    return errors


def validate_grounding(
    *,
    modelmemory: bool,
    content_passed: bool,
    response: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    if not modelmemory:
        if not content_passed:
            errors.append("modelmemory=false requires content")
        if response.get("modelmemory_used") is True:
            errors.append("modelmemory_used must be false when modelmemory=false")
        if response.get("grounded") is not True:
            errors.append("grounded must be true when modelmemory=false")
        if content_passed and not response.get("citations"):
            errors.append("citations required when content is passed and modelmemory=false")
    return errors
