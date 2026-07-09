"""
The cheap, no-LLM gate: should this message pay for a Tier 2 (Gemma) round-trip?

Tier 2 is a 400ms-1.5s LLM call, so we do NOT run it on every message. This is the
PRIMARY gate (plan.md "Tier routing"): a fast, local risk signal from trigger
words, fenced code, high-entropy secret-like tokens, message length, and the
conversation's rising session risk. The engine also runs Tier 2 on an ambiguous
Tier 1 hit, but that is a *secondary* gate — this heuristic is the main one.

Public API:
    assess(text, *, session_risk=0.0) -> Heuristic   # .fire, .score, .reasons
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

# Phrases that suggest contextual sensitivity regex can't structurally catch.
_TRIGGERS = (
    "confidential",
    "do not share",
    "do not distribute",
    "internal only",
    "internal use only",
    "proprietary",
    "classified",
    "nda",
    "under embargo",
    "undisclosed",
    "pre-earnings",
    "acquisition",
    "acquiring",
    "merger",
    "not public",
    "keep this quiet",
)

_FIRE_THRESHOLD = 0.3
_SESSION_FORCE = 0.7
_TOKEN_RE = re.compile(r"\S+")


@dataclass
class Heuristic:
    fire: bool
    score: float
    reasons: list[str] = field(default_factory=list)


def _shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    counts = {c: s.count(c) for c in set(s)}
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def _has_high_entropy_token(text: str) -> bool:
    """A long, mixed-case-alnum, high-entropy token that matched no known pattern."""
    for tok in _TOKEN_RE.findall(text):
        core = tok.strip(".,:;\"'()[]{}")
        if (
            len(core) >= 20
            and any(c.isalpha() for c in core)
            and any(c.isdigit() for c in core)
            and _shannon_entropy(core) >= 3.5
        ):
            return True
    return False


def assess(text: str, *, session_risk: float = 0.0) -> Heuristic:
    reasons: list[str] = []
    score = 0.0
    lowered = text.lower()

    for phrase in _TRIGGERS:
        if phrase in lowered:
            reasons.append(f"trigger:{phrase}")
            score += 0.4

    if "```" in text:
        reasons.append("fenced_code_block")
        score += 0.3

    if _has_high_entropy_token(text):
        reasons.append("high_entropy_token")
        score += 0.3

    if len(text) > 800:
        reasons.append("long_message")
        score += 0.1

    if session_risk >= _SESSION_FORCE:
        reasons.append("elevated_session_risk")
        score += session_risk

    score = min(1.0, score)
    fire = score >= _FIRE_THRESHOLD or session_risk >= _SESSION_FORCE
    return Heuristic(fire=fire, score=score, reasons=reasons)
