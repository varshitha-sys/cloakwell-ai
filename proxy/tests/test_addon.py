"""
Tests for the mitmproxy addon's pure helpers (proxy/addon.py).

The flow-handling method needs a live mitmproxy; these cover the testable seams it
delegates to: pulling the prompt out of an intercepted body, rewriting that body
with redacted text, and mapping a label to a proxy action.
"""
import addon


def test_extract_prompt_from_plain_string_content():
    body = {"model": "x", "messages": [{"role": "user", "content": "my ssn is 123-45-6789"}]}
    assert "123-45-6789" in addon.extract_prompt(body)


def test_extract_prompt_from_content_blocks():
    body = {"messages": [{"role": "user", "content": [{"type": "text", "text": "hello Falcon"}]}]}
    assert "hello Falcon" in addon.extract_prompt(body)


def test_extract_prompt_uses_last_user_message():
    body = {
        "messages": [
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "ok"},
            {"role": "user", "content": "second"},
        ]
    }
    assert addon.extract_prompt(body).strip() == "second"


def test_extract_prompt_empty_when_no_user_message():
    assert addon.extract_prompt({"messages": [{"role": "assistant", "content": "hi"}]}) == ""


def test_apply_redaction_rewrites_last_user_content_without_mutating_original():
    body = {"messages": [{"role": "user", "content": "leak sk-abc"}]}
    new = addon.apply_redaction(body, "leak [REDACTED_API_KEY_1]")
    assert new["messages"][-1]["content"] == "leak [REDACTED_API_KEY_1]"
    assert body["messages"][-1]["content"] == "leak sk-abc"  # original untouched


def test_decide_maps_labels_to_actions():
    assert addon.decide({"label": "INFO"}) == "forward"
    assert addon.decide({"label": "WARN"}) == "forward"
    assert addon.decide({"label": "ACTION_NEEDED"}) == "redact"
    assert addon.decide({"label": "BLOCK"}) == "block"
