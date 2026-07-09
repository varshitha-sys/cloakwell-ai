"""
Smart redaction: swap detected sensitive values for named, reversible placeholders.

Deletion would break the prompt's usefulness to the model, so we substitute
``[REDACTED_<TYPE>_<n>]`` placeholders and keep a ``placeholder -> value`` mapping
so the original can be restored locally (see architecture.md's reversible-swap
design). Works off entity ``value`` strings, so it uniformly handles Tier 1 (regex),
watchlist, and Tier 2 (LLM) hits regardless of whether they carry char offsets.

Public API:
    redact(text, entities) -> Redaction     # .redacted_text, .mapping
    unredact(text, mapping) -> str
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Redaction:
    redacted_text: str
    mapping: dict = field(default_factory=dict)  # placeholder -> original value


def redact(text: str, entities: list[dict]) -> Redaction:
    """
    Replace each entity's ``value`` in ``text`` with a typed placeholder.

    Longest values are replaced first so a shorter value that is a substring of a
    longer one can't corrupt it. Identical values share one placeholder (and every
    occurrence is replaced), keeping the mapping reversible.
    """
    redacted = text
    mapping: dict[str, str] = {}
    value_to_placeholder: dict[str, str] = {}
    counters: dict[str, int] = {}

    for ent in sorted(entities, key=lambda e: len(str(e.get("value") or "")), reverse=True):
        value = ent.get("value")
        etype = ent.get("type", "SENSITIVE")
        if not value:
            continue
        if value in value_to_placeholder:
            continue  # already assigned + replaced on a previous pass
        if value not in redacted:
            continue
        counters[etype] = counters.get(etype, 0) + 1
        placeholder = f"[REDACTED_{etype}_{counters[etype]}]"
        value_to_placeholder[value] = placeholder
        mapping[placeholder] = value
        redacted = redacted.replace(value, placeholder)

    return Redaction(redacted_text=redacted, mapping=mapping)


def unredact(text: str, mapping: dict) -> str:
    """Restore placeholders in ``text`` back to their original values."""
    restored = text
    for placeholder, value in mapping.items():
        restored = restored.replace(placeholder, value)
    return restored
