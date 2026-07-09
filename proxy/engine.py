"""
Classification core — the shared detection pipeline behind BOTH entrypoints.

api.py exposes this over HTTP (/classify) for the extension + dashboard; addon.py
calls it in-process (no HTTP hop) on intercepted CLI-tool traffic. Keeping the
pipeline here means the proxy and the API can never drift apart.

Pipeline (see plan.md "Tier routing"):
  1. Tier 1 (regex) + org watchlist  -> deterministic structured/terminology hits
  2. Rule-grade those hits            -> a baseline label with no LLM
  3. Cheap heuristic gate             -> decide if a Tier 2 LLM call is warranted
  4. Tier 2 (Gemma) ONLY when gated   -> contextual grading; take the max label
  5. Redact every detected value      -> reversible [REDACTED_*] placeholders
  6. Update conversation session risk -> rising context can bump future messages

Public API:
    classify(text, *, session_id="default", source="proxy", policy=None,
             tier2_client=None) -> dict
        {label, entities, redacted_text, confidence, tier, session_risk, reasons}
"""
from __future__ import annotations

import heuristic
import policy as policy_module
import redactor
import session as session_module
import tier1
import tier2

# --- Severity model -------------------------------------------------------

_ORDER = {"INFO": 0, "WARN": 1, "ACTION_NEEDED": 2, "BLOCK": 3}

# What each entity type is worth on its own, before any contextual grading.
_SEVERITY = {
    # Tier 1 secrets — sharing live credentials is a hard block.
    "API_KEY": "BLOCK",
    "AWS_ACCESS_KEY": "BLOCK",
    "GITHUB_TOKEN": "BLOCK",
    "GCP_API_KEY": "BLOCK",
    "PASSWORD": "BLOCK",
    "AUTH_URL": "BLOCK",
    # Tier 1 financial / national identifiers — redact before sending.
    "CREDIT_CARD": "ACTION_NEEDED",
    "SSN": "ACTION_NEEDED",
    "AADHAAR": "ACTION_NEEDED",
    "PAN": "ACTION_NEEDED",
    # Tier 1 contact PII — mild; context (Tier 2) may escalate.
    "EMAIL": "WARN",
    "IP_ADDRESS": "WARN",
    "INDIAN_PHONE": "WARN",
    # Org watchlist / Tier 2 contextual types.
    "GOV_CREDENTIAL": "BLOCK",
    "PROJECT_CODENAME": "ACTION_NEEDED",
    "ACQUISITION": "ACTION_NEEDED",
    "INTERNAL_INFRA": "ACTION_NEEDED",
    "ORG_SENSITIVE": "WARN",
    "PERSON_NAME": "WARN",
}

_LABEL_RISK = {"INFO": 0.0, "WARN": 0.4, "ACTION_NEEDED": 0.7, "BLOCK": 1.0}

# Process-scoped state. In-memory only; never persisted.
_tracker = session_module.SessionTracker()
_default_policy = policy_module.load_policy()


def _max_label(a: str, b: str) -> str:
    return a if _ORDER[a] >= _ORDER[b] else b


def _severity(etype: str) -> str:
    return _SEVERITY.get(etype, "WARN")


def _rule_label(entities: list[dict]) -> str:
    label = "INFO"
    for e in entities:
        label = _max_label(label, _severity(e.get("type", "")))
    return label


def _dedupe(entities: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    out: list[dict] = []
    for e in entities:
        key = (e.get("type"), e.get("value"))
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out


def classify(
    text: str,
    *,
    session_id: str = "default",
    source: str = "proxy",
    context=None,
    policy=None,
    tier2_client=None,
) -> dict:
    pol = policy if policy is not None else _default_policy

    # 1. Deterministic detection: Tier 1 regex + org watchlist.
    structured = tier1.detect(text)
    structured += policy_module.match_watchlist(text, getattr(pol, "watchlist", []))
    rule_label = _rule_label(structured)

    # 2. Decide whether to spend a Tier 2 LLM call.
    prior_risk = _tracker.risk(session_id)
    heur = heuristic.assess(text, session_risk=prior_risk)
    ambiguous_tier1 = rule_label == "WARN"  # a mild hit context might worsen
    # Already-BLOCK is unambiguous and maximal — nothing for Tier 2 to add.
    run_tier2 = rule_label != "BLOCK" and (heur.fire or ambiguous_tier1)

    label = rule_label
    confidence = 0.99
    tier = "tier1"
    contextual_entities: list[dict] = []
    reasons = list(heur.reasons)

    # 3. Tier 2 (Gemma) — contextual grading, only when gated.
    if run_tier2:
        tier = "tier2"
        t2 = tier2.classify(text, context=context, tier1_entities=structured,
                            policy=pol, client=tier2_client)
        label = _max_label(rule_label, t2["label"])
        confidence = t2["confidence"]
        contextual_entities = t2["entities"]
        if t2.get("reasoning"):
            reasons.append(f"tier2:{t2['reasoning']}")

    # 4. Combine entities and redact every detected value.
    entities = _dedupe(structured + contextual_entities)
    redaction = redactor.redact(text, entities)

    # 5. Update conversation-level running risk (post-message).
    session_risk = _tracker.update(session_id, _LABEL_RISK[label])

    return {
        "label": label,
        "entities": entities,
        "redacted_text": redaction.redacted_text,
        "redaction_map": redaction.mapping,
        "confidence": confidence,
        "tier": tier,
        "session_risk": session_risk,
        "source": source,
        "reasons": reasons,
    }
