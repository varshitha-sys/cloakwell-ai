"""
Tier 1: local, dependency-free regex PII/secrets detection engine.

Runs on EVERY intercepted message (Tier 2 — the Gemma LLM classifier — only runs
when this flags something, to avoid an LLM round-trip per message).

Public API:
    detect(text) -> list[dict]   # [{"type", "value", "start", "end"}, ...]

Entities carry character offsets so downstream redaction can do exact,
span-based replacement (see redactor.py) rather than fragile substring swaps.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Checksum validators — cut false positives on structured numbers.
# ---------------------------------------------------------------------------


def _luhn(number: str) -> bool:
    """Standard mod-10 (Luhn) check used by credit-card numbers."""
    digits = [int(d) for d in number if d.isdigit()]
    if len(digits) < 13:
        return False
    checksum = 0
    # Double every second digit from the right.
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


# Verhoeff checksum tables (d = multiplication, p = permutation, inv unused here).
_VERHOEFF_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_VERHOEFF_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]


def _verhoeff(number: str) -> bool:
    """Verhoeff checksum used by India's 12-digit Aadhaar number."""
    digits = [int(d) for d in number if d.isdigit()]
    if len(digits) != 12:
        return False
    check = 0
    # Process digits right-to-left, position starting at 0.
    for i, d in enumerate(reversed(digits)):
        check = _VERHOEFF_D[check][_VERHOEFF_P[i % 8][d]]
    return check == 0


# ---------------------------------------------------------------------------
# Pattern library — (TYPE, compiled_regex, optional_validator).
# Order matters only as a tie-break hint; overlap resolution keeps the longest,
# most-specific match. Validators receive the full matched string.
# ---------------------------------------------------------------------------

_PATTERNS: list[tuple[str, re.Pattern, "callable | None"]] = [
    # Credentials / secrets first (most specific, high-value).
    ("AWS_ACCESS_KEY", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), None),
    ("GITHUB_TOKEN", re.compile(r"\bgh[posur]_[A-Za-z0-9]{36,}\b"), None),
    ("GCP_API_KEY", re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b"), None),
    ("API_KEY", re.compile(r"\bsk-[A-Za-z0-9\-]{20,}\b"), None),
    # URLs carrying auth, and credentials embedded in URLs.
    (
        "AUTH_URL",
        re.compile(
            r"https?://[^\s]*[?&](?:token|api_key|apikey|access_token|auth)=[^\s&]+"
            r"|https?://[^\s:@/]+:[^\s:@/]+@[^\s]+"
        ),
        None,
    ),
    # password=... / password: ...
    ("PASSWORD", re.compile(r"(?i)\bpass(?:word|wd)?\s*[:=]\s*\S+"), None),
    # Structured numbers (checksum-validated where possible).
    (
        "CREDIT_CARD",
        # Start and end on a digit so trailing separators aren't captured.
        re.compile(r"\b\d(?:[ -]?\d){12,15}\b"),
        lambda m: _luhn(m),
    ),
    (
        "AADHAAR",
        re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"),
        lambda m: _verhoeff(m),
    ),
    ("PAN", re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"), None),
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), None),
    (
        "INDIAN_PHONE",
        # Optional +91 / 0 prefix, then a 10-digit mobile (starts 6-9) that may
        # carry one internal space or dash, e.g. "+91 98765 43210".
        re.compile(r"(?:(?:\+|0)?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}\b"),
        None,
    ),
    (
        "IP_ADDRESS",
        re.compile(
            r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"
        ),
        None,
    ),
    (
        "EMAIL",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        None,
    ),
]


def detect(text: str) -> list[dict]:
    """
    Find all sensitive entities in ``text``.

    Returns a list of ``{"type", "value", "start", "end"}`` dicts sorted by
    start offset, with overlapping matches resolved in favour of the longest,
    most-specific one (e.g. a Luhn-valid CREDIT_CARD beats a bare number).
    """
    candidates: list[dict] = []
    for etype, pattern, validator in _PATTERNS:
        for m in pattern.finditer(text):
            value = m.group(0)
            if validator is not None and not validator(value):
                continue
            candidates.append(
                {"type": etype, "value": value, "start": m.start(), "end": m.end()}
            )

    # Overlap resolution: prefer longer spans; greedily keep non-overlapping.
    candidates.sort(key=lambda e: (e["start"], -(e["end"] - e["start"])))
    kept: list[dict] = []
    occupied_end = -1
    for ent in sorted(candidates, key=lambda e: (-(e["end"] - e["start"]), e["start"])):
        if all(ent["end"] <= k["start"] or ent["start"] >= k["end"] for k in kept):
            kept.append(ent)

    kept.sort(key=lambda e: e["start"])
    return kept


if __name__ == "__main__":
    import json

    samples = [
        # Repo canonical string.
        "Summarise this complaint from Jane Doe, SSN 123-45-6789, about our "
        "unreleased Project Falcon delay. Her email is jane.doe@example.com and "
        "our API key sk-abc123xyz789def456ghi was mentioned by mistake.",
        # India-focused PII.
        "My Aadhaar is 9999 4105 7058, PAN ABCDE1234F, call me on +91 98765 43210.",
        # Secrets / infra.
        "Deploy key AKIAIOSFODNN7EXAMPLE and token ghp_1234567890abcdefghijklmnopqrstuvwxyz "
        "to server 192.168.1.20 with password=hunter2.",
        "Fetch https://api.example.com/data?api_key=SECRET123&x=1 for the report.",
        # Valid credit card (Luhn ok): 4242 4242 4242 4242.
        "Charge card 4242 4242 4242 4242 today.",
    ]
    for s in samples:
        print("=" * 70)
        print(s)
        print(json.dumps(detect(s), indent=2))
