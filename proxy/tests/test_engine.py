"""
Tests for the shared classification core (engine.classify).

engine orchestrates: Tier 1 (always) + watchlist + the heuristic gate + Tier 2
(only when gated) + redaction + session risk. Tier 2 is exercised via an injected
fake client so these run offline. A client that raises AssertionError is used to
PROVE Tier 2 is not called on the fast path.
"""
import json

import engine
import policy


def _tier2_returning(label, entities=None):
    payload = {"label": label, "confidence": 0.9, "reasoning": "x", "entities": entities or []}
    return lambda messages: json.dumps(payload)


def _forbid_tier2(messages):
    raise AssertionError("Tier 2 must not run for this input")


def test_benign_message_consults_tier2_and_stays_info():
    # Default-on posture: even a benign prompt is shown to Gemma (the heuristic is
    # no longer a gate). Gemma agrees it's INFO, so the verdict is INFO via tier2.
    out = engine.classify("what's the weather like today?", session_id="t-benign",
                          tier2_client=_tier2_returning("INFO"))
    assert out["label"] == "INFO"
    assert out["tier"] == "tier2"


def test_unambiguous_secret_blocks_deterministically_without_llm():
    out = engine.classify("my key is sk-abc123xyz789def456ghi ok?", session_id="t-secret",
                          tier2_client=_forbid_tier2)
    assert out["label"] == "BLOCK"
    assert any(e["type"] == "API_KEY" for e in out["entities"])
    assert "sk-abc123xyz789def456ghi" not in out["redacted_text"]


def test_watchlist_term_caught_and_tier2_still_consulted():
    # A watchlist hit is ACTION_NEEDED by rule -- not maximal (only BLOCK is), so
    # under the default-on posture Gemma is still consulted (it may escalate or add
    # context). The deterministic redaction stands regardless of what Tier 2 says.
    pol = policy.Policy(statement="", watchlist=[{"term": "Project Falcon", "type": "PROJECT_CODENAME"}])
    out = engine.classify("draft the Project Falcon memo", session_id="t-wl", policy=pol,
                          tier2_client=_tier2_returning("INFO"))
    assert out["tier"] == "tier2"
    assert out["label"] == "ACTION_NEEDED"   # max(rule ACTION_NEEDED, tier2 INFO)
    assert "[REDACTED_PROJECT_CODENAME_1]" in out["redacted_text"]


def test_heuristic_trigger_runs_tier2_and_takes_the_max_label():
    out = engine.classify("please keep this strictly confidential", session_id="t-trig",
                          tier2_client=_tier2_returning("ACTION_NEEDED"))
    assert out["tier"] == "tier2"
    assert out["label"] == "ACTION_NEEDED"


def test_ambiguous_warn_tier1_hit_escalates_via_tier2():
    # A bare email is WARN by rule; context could worsen it -> Tier 2 runs (secondary gate).
    out = engine.classify("reach jane@example.com", session_id="t-amb",
                          tier2_client=_tier2_returning("ACTION_NEEDED"))
    assert out["tier"] == "tier2"
    assert out["label"] == "ACTION_NEEDED"


def test_tier2_failure_never_raises_and_falls_back():
    def boom(messages):
        raise RuntimeError("fireworks down")

    out = engine.classify("keep this confidential", session_id="t-fail", tier2_client=boom)
    assert out["label"] == "WARN"          # Tier 2 safe default, maxed with INFO rule
    assert out["tier"] == "tier2"


def test_session_risk_accumulates_across_a_thread():
    sid = "t-accum"
    r1 = engine.classify("keep this confidential", session_id=sid,
                         tier2_client=_tier2_returning("ACTION_NEEDED"))["session_risk"]
    r2 = engine.classify("again, strictly confidential", session_id=sid,
                         tier2_client=_tier2_returning("ACTION_NEEDED"))["session_risk"]
    assert 0.0 < r1 <= r2 <= 1.0


def test_output_contract_has_all_fields():
    out = engine.classify("hello there", session_id="t-contract",
                          tier2_client=_tier2_returning("INFO"))
    for key in ("label", "entities", "redacted_text", "confidence", "tier", "session_risk"):
        assert key in out
