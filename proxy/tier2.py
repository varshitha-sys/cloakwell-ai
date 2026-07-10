"""
Tier 2: contextual sensitivity classifier via Gemma on AMD MI300X (Fireworks AI).

Tier 1 (tier1.py) catches STRUCTURED data (SSNs, cards, keys) with regex and is
structurally blind to CONTEXTUAL leaks that have no fixed shape: project
codenames, "we're acquiring Acme Friday", internal infra, "the usual prod creds".
Tier 2 is the LLM that judges exactly that, and grades severity into one of four
labels. It is an LLM round-trip (~400ms-1.5s), so callers run it ONLY when gated
(a cheap heuristic fires, or a Tier 1 hit's severity is ambiguous) -- that gating
lives in api.py, not here.

Org-awareness (no RAG): the org's `policy.statement` is injected into the system
prompt so Gemma judges against THIS org's rules, and known sensitive terms from
the watchlist are listed for grounding. See policy.py.

Public API:
    classify(text, *, context=None, tier1_entities=None, policy=None, client=None) -> dict

Returns: {"label", "confidence", "reasoning", "tier": "tier2", "entities": [...]}
where each entity is {"type", "value", "start", "end"} with spans localized in
`text` (start/end None if the value can't be located), mirroring tier1.detect.
"""
from __future__ import annotations

import json
import os
import re
from typing import Callable

LABELS = ("INFO", "WARN", "ACTION_NEEDED", "BLOCK")

# Controlled vocabulary for contextual entities. Well-formed structured PII stays
# Tier 1's job; CREDENTIAL is the safety-net type for a live secret a user is
# clearly sharing whose shape regex didn't recognise (see the system prompt).
ENTITY_TYPES = (
    "PROJECT_CODENAME",
    "ACQUISITION",
    "INTERNAL_INFRA",
    "GOV_CREDENTIAL",
    "CREDENTIAL",
    "ORG_SENSITIVE",
    "PERSON_NAME",
)

_DEFAULT_MODEL = "accounts/fireworks/models/gemma-4-31b-it"
_DEFAULT_BASE_URL = "https://api.fireworks.ai/inference/v1"

_BASE_SYSTEM_PROMPT = f"""\
You are a Data Loss Prevention (DLP) classifier. You judge whether a message a \
user is about to send to an external AI tool contains CONTEXTUAL / SEMANTIC \
sensitive information -- the kind that has no fixed pattern (project codenames, \
undisclosed acquisitions, internal infrastructure, "the usual prod creds", \
unreleased plans).

A fast regex layer already catches WELL-FORMED structured PII (SSNs, credit \
cards, and standard-format keys such as sk-... or AKIA...), so you need not \
re-flag those. But you are the SAFETY NET for secrets regex cannot match: if a \
user is clearly sharing a live credential -- an API key, password, token, access \
key, or similar secret -- whose shape is non-standard (e.g. "my apikey is \
EAMPSLEDUMYY"), you MUST flag it as a CREDENTIAL. Never let a secret slip merely \
because its shape is unusual, and treat a user plainly handing over a live \
credential as a severe leak (BLOCK).

Assign exactly one severity label:
- INFO: benign, no sensitive context.
- WARN: mildly sensitive; log and let the user decide.
- ACTION_NEEDED: clearly sensitive; the sensitive parts should be redacted before sending.
- BLOCK: severe leak (e.g. sharing live credentials / classified data); must not be sent.

For each sensitive span, emit an entity with a "type" from this set: \
{", ".join(ENTITY_TYPES)}.

Respond with ONLY a JSON object, no prose, in exactly this schema:
{{"label": "<one label>", "confidence": <0..1>, "reasoning": "<short>", \
"entities": [{{"type": "<type>", "value": "<verbatim text>"}}]}}"""


def build_system_prompt(policy=None) -> str:
    """Base classifier instructions, augmented with the org's policy + watchlist."""
    prompt = _BASE_SYSTEM_PROMPT
    if policy is not None:
        if getattr(policy, "statement", ""):
            prompt += f"\n\nThis organisation's confidentiality policy:\n{policy.statement.strip()}"
        terms = [w.get("term", "") for w in getattr(policy, "watchlist", []) if w.get("term")]
        if terms:
            prompt += (
                "\n\nKnown organisation-sensitive terms (treat any mention as sensitive): "
                + ", ".join(terms)
            )
    return prompt


def build_messages(text, *, context=None, tier1_entities=None, policy=None) -> list[dict]:
    """Assemble the chat messages: system + optional context/Tier-1 hints + user."""
    messages = [{"role": "system", "content": build_system_prompt(policy)}]

    if context:
        thread = "\n".join(str(c) for c in context)
        messages.append(
            {"role": "user", "content": f"Earlier in this conversation:\n{thread}"}
        )
    if tier1_entities:
        found = ", ".join(sorted({e.get("type", "") for e in tier1_entities}))
        messages.append(
            {
                "role": "user",
                "content": f"(Structured PII already detected by regex: {found}. "
                "Grade the contextual severity given this.)",
            }
        )

    messages.append({"role": "user", "content": text})
    return messages


def _safe_default(reasoning: str) -> dict:
    """Fail-safe result used when the LLM output is unusable or the call fails."""
    return {
        "label": "WARN",
        "confidence": 0.3,
        "reasoning": reasoning,
        "tier": "tier2",
        "entities": [],
    }


def _extract_json(raw: str) -> str | None:
    """Pull a JSON object out of raw model output (tolerating ```json fences)."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if fenced:
        return fenced.group(1)
    brace = re.search(r"\{.*\}", raw, re.DOTALL)
    return brace.group(0) if brace else None


def _localize(entity: dict, text: str) -> dict:
    """Attach start/end offsets by finding the entity value in ``text``."""
    value = str(entity.get("value", ""))
    etype = entity.get("type", "ORG_SENSITIVE")
    idx = text.lower().find(value.lower()) if value else -1
    if idx == -1:
        return {"type": etype, "value": value, "start": None, "end": None}
    end = idx + len(value)
    # Preserve the source text's exact casing for span-based redaction.
    return {"type": etype, "value": text[idx:end], "start": idx, "end": end}


def parse_response(raw: str, text: str) -> dict:
    """
    Parse raw Gemma output into the Tier 2 result dict.

    Robust to markdown fences and stray prose; clamps the label to LABELS and
    confidence to [0,1]; localizes entity spans in ``text``. Any failure yields a
    fail-safe WARN so a bad LLM response never breaks the request path.
    """
    blob = _extract_json(raw or "")
    if blob is None:
        return _safe_default("tier2 parse failed: no JSON in response")
    try:
        data = json.loads(blob)
    except (ValueError, TypeError):
        return _safe_default("tier2 parse failed: invalid JSON")

    label = data.get("label")
    if label not in LABELS:
        label = "WARN"

    try:
        confidence = float(data.get("confidence", 0.5))
    except (ValueError, TypeError):
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))

    entities = [
        _localize(e, text)
        for e in (data.get("entities") or [])
        if isinstance(e, dict) and e.get("value")
    ]

    return {
        "label": label,
        "confidence": confidence,
        "reasoning": str(data.get("reasoning", "")),
        "tier": "tier2",
        "entities": entities,
    }


_openai_client = None


def _get_client():
    """
    Lazily build and cache the OpenAI-SDK client pointed at Fireworks.

    Fireworks exposes an OpenAI-compatible API, so we use the official ``openai``
    SDK (retries + connection pooling for free) rather than hand-rolling HTTP. The
    import is lazy so tier2's pure functions (build_messages/parse_response) import
    fine without the SDK installed. Caching reuses one pooled connection per process.
    """
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI

        _openai_client = OpenAI(
            api_key=os.environ["FIREWORKS_API_KEY"],  # KeyError -> caught by classify()
            base_url=os.getenv("FIREWORKS_BASE_URL", _DEFAULT_BASE_URL),
        )
    return _openai_client


def _fireworks_client(messages: list[dict]) -> str:
    """Default client: one chat completion via the OpenAI SDK, return content."""
    resp = _get_client().chat.completions.create(
        model=os.getenv("FIREWORKS_MODEL", _DEFAULT_MODEL),
        messages=messages,
        temperature=0,
        max_tokens=2048,
        response_format={"type": "json_object"},
    )
    return resp.choices[0].message.content


def classify(
    text: str,
    *,
    context=None,
    tier1_entities=None,
    policy=None,
    client: Callable[[list[dict]], str] | None = None,
) -> dict:
    """
    Classify ``text`` for contextual sensitivity.

    ``client`` is an injectable ``messages -> raw_content`` callable (tests pass a
    fake; production leaves it None to hit Fireworks). Any client/parse failure
    returns a fail-safe WARN rather than raising into the request path.
    """
    call = client or _fireworks_client
    messages = build_messages(
        text, context=context, tier1_entities=tier1_entities, policy=policy
    )
    try:
        raw = call(messages)
    except Exception as exc:  # network, auth, timeout, missing key -> fail safe
        return _safe_default(f"tier2 unavailable: {type(exc).__name__}")
    return parse_response(raw, text)


if __name__ == "__main__":
    import policy as _policy

    pol = _policy.load_policy()
    samples = [
        "Can you refactor this Python function to be faster?",              # INFO
        "Draft an email announcing the Project Falcon launch next month.",  # codename
        "Keep the Acme Corp acquisition confidential until we announce.",   # M&A
        "SSH into prod-db-07.initech.internal with the usual prod creds.",  # infra + creds
    ]
    for s in samples:
        print("=" * 70)
        print(s)
        print(json.dumps(classify(s, policy=pol), indent=2))
