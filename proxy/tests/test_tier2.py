"""
Tests for Tier 2: the Gemma contextual classifier.

All default tests run OFFLINE via an injected fake ``client`` (a callable
``messages -> raw_content``) so no network or API key is needed. A single live
test hits real Fireworks and is skipped unless FIREWORKS_LIVE=1 is set.
"""
import json
import os

import pytest

import policy
import tier2


def _fake_client(raw):
    """Build a client callable that ignores messages and returns ``raw``."""
    return lambda messages: raw


# --- Prompt construction --------------------------------------------------


def test_build_messages_has_system_first_and_user_with_text():
    msgs = tier2.build_messages("we are acquiring Globex on Friday")
    assert msgs[0]["role"] == "system"
    assert msgs[-1]["role"] == "user"
    assert "acquiring Globex" in msgs[-1]["content"]


def test_system_prompt_injects_org_policy_and_watchlist():
    pol = policy.Policy(
        statement="Pricing is confidential.",
        watchlist=[{"term": "Project Falcon", "type": "PROJECT_CODENAME"}],
    )
    prompt = tier2.build_system_prompt(pol)
    assert "Pricing is confidential." in prompt
    assert "Project Falcon" in prompt


def test_system_prompt_without_policy_still_lists_labels():
    prompt = tier2.build_system_prompt(None)
    for label in ("INFO", "WARN", "ACTION_NEEDED", "BLOCK"):
        assert label in prompt


# --- Response parsing -----------------------------------------------------


def test_parse_clean_json():
    raw = json.dumps(
        {"label": "WARN", "confidence": 0.9, "reasoning": "codename", "entities": []}
    )
    out = tier2.parse_response(raw, "text")
    assert out["label"] == "WARN"
    assert out["confidence"] == 0.9
    assert out["tier"] == "tier2"


def test_parse_strips_markdown_fences():
    raw = '```json\n{"label": "BLOCK", "confidence": 1, "reasoning": "x", "entities": []}\n```'
    assert tier2.parse_response(raw, "text")["label"] == "BLOCK"


def test_parse_fenced_json_with_nested_entity_objects():
    # ```json fences AND entities containing objects: the extractor must grab the
    # whole outer object, not stop at the first inner "}".
    text = "Ship Project Falcon on Friday."
    raw = (
        "```json\n"
        + json.dumps(
            {
                "label": "ACTION_NEEDED",
                "confidence": 0.9,
                "reasoning": "codename",
                "entities": [{"type": "PROJECT_CODENAME", "value": "Project Falcon"}],
            }
        )
        + "\n```"
    )
    out = tier2.parse_response(raw, text)
    assert out["label"] == "ACTION_NEEDED"
    assert out["entities"][0]["value"] == "Project Falcon"


def test_parse_localizes_entity_spans_in_text():
    text = "Keep the Project Falcon launch quiet."
    raw = json.dumps(
        {
            "label": "ACTION_NEEDED",
            "confidence": 0.8,
            "reasoning": "codename",
            "entities": [{"type": "PROJECT_CODENAME", "value": "Project Falcon"}],
        }
    )
    ent = tier2.parse_response(raw, text)["entities"][0]
    assert text[ent["start"]:ent["end"]] == "Project Falcon"


def test_parse_entity_not_in_text_gets_null_span():
    raw = json.dumps(
        {
            "label": "WARN",
            "confidence": 0.5,
            "reasoning": "x",
            "entities": [{"type": "ORG_SENSITIVE", "value": "not present here"}],
        }
    )
    ent = tier2.parse_response(raw, "totally different text")["entities"][0]
    assert ent["start"] is None and ent["end"] is None


def test_parse_clamps_unknown_label_to_warn():
    raw = json.dumps(
        {"label": "SUPER_BAD", "confidence": 0.5, "reasoning": "x", "entities": []}
    )
    assert tier2.parse_response(raw, "text")["label"] == "WARN"


def test_parse_clamps_confidence_to_unit_range():
    raw = json.dumps(
        {"label": "INFO", "confidence": 5, "reasoning": "x", "entities": []}
    )
    assert tier2.parse_response(raw, "text")["confidence"] == 1.0


def test_parse_malformed_returns_safe_default():
    out = tier2.parse_response("not json at all {", "text")
    assert out["label"] == "WARN"
    assert out["entities"] == []
    assert out["confidence"] <= 0.5


# --- classify() orchestration (offline, injected client) ------------------


def test_classify_end_to_end_with_injected_client():
    text = "We are acquiring Acme Corp next week; keep it quiet."
    raw = json.dumps(
        {
            "label": "ACTION_NEEDED",
            "confidence": 0.88,
            "reasoning": "undisclosed acquisition",
            "entities": [{"type": "ACQUISITION", "value": "Acme Corp"}],
        }
    )
    out = tier2.classify(text, client=_fake_client(raw))
    assert out["label"] == "ACTION_NEEDED"
    assert out["entities"][0]["type"] == "ACQUISITION"
    assert text[out["entities"][0]["start"]:out["entities"][0]["end"]] == "Acme Corp"


def test_classify_survives_client_error_with_safe_default():
    def boom(messages):
        raise RuntimeError("fireworks down")

    out = tier2.classify("anything", client=boom)
    assert out["label"] == "WARN"          # fail safe, do not raise into request path
    assert out["tier"] == "tier2"


def test_default_client_falls_back_when_api_key_missing(monkeypatch):
    # No injected client + no FIREWORKS_API_KEY: the real default client must fail
    # safe (no network, no key access crash bubbling into the request path).
    monkeypatch.delenv("FIREWORKS_API_KEY", raising=False)
    out = tier2.classify("keep the Acme Corp deal quiet")
    assert out["label"] == "WARN"
    assert "unavailable" in out["reasoning"]


# --- Live smoke test (opt-in) ---------------------------------------------


@pytest.mark.skipif(
    not os.getenv("FIREWORKS_LIVE"),
    reason="live test; opt in with FIREWORKS_LIVE=1 (creds come from .env)",
)
def test_live_classify_catches_contextual_leak():
    out = tier2.classify(
        "Reminder: keep the Acme Corp acquisition confidential until the announcement.",
        policy=policy.load_policy(),
    )
    assert out["label"] in ("WARN", "ACTION_NEEDED", "BLOCK")
