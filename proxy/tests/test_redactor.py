"""Tests for the smart redactor: named placeholders + reversible mapping."""
import redactor


def test_redacts_entity_with_named_numbered_placeholder():
    text = "email me at jane@example.com please"
    ents = [{"type": "EMAIL", "value": "jane@example.com", "start": 12, "end": 28}]
    r = redactor.redact(text, ents)
    assert "jane@example.com" not in r.redacted_text
    assert "[REDACTED_EMAIL_1]" in r.redacted_text
    assert r.mapping["[REDACTED_EMAIL_1]"] == "jane@example.com"


def test_two_distinct_values_get_numbered_placeholders():
    text = "from a@x.com to b@x.com"
    ents = [{"type": "EMAIL", "value": "a@x.com"}, {"type": "EMAIL", "value": "b@x.com"}]
    r = redactor.redact(text, ents)
    assert "[REDACTED_EMAIL_1]" in r.redacted_text
    assert "[REDACTED_EMAIL_2]" in r.redacted_text
    assert len(r.mapping) == 2


def test_identical_value_reuses_one_placeholder_for_all_occurrences():
    text = "ping 192.168.1.20, retry 192.168.1.20"
    ents = [{"type": "IP_ADDRESS", "value": "192.168.1.20"}]
    r = redactor.redact(text, ents)
    assert r.redacted_text.count("[REDACTED_IP_ADDRESS_1]") == 2
    assert len(r.mapping) == 1


def test_longer_value_replaced_before_its_substring():
    text = "ship Project Falcon, not Falcon alone"
    ents = [
        {"type": "CODE", "value": "Falcon"},
        {"type": "PROJECT_CODENAME", "value": "Project Falcon"},
    ]
    r = redactor.redact(text, ents)
    # The full codename must not survive as a side effect of replacing "Falcon" first.
    assert "Project Falcon" not in r.redacted_text
    assert "[REDACTED_PROJECT_CODENAME_1]" in r.redacted_text


def test_unredact_round_trips_to_original():
    text = "Contact jane@example.com about Project Falcon."
    ents = [
        {"type": "EMAIL", "value": "jane@example.com"},
        {"type": "PROJECT_CODENAME", "value": "Project Falcon"},
    ]
    r = redactor.redact(text, ents)
    assert redactor.unredact(r.redacted_text, r.mapping) == text


def test_entities_without_a_usable_value_are_skipped():
    r = redactor.redact("hello world", [{"type": "X"}, {"type": "Y", "value": ""}])
    assert r.redacted_text == "hello world"
    assert r.mapping == {}


def test_value_absent_from_text_is_skipped():
    r = redactor.redact("plain text", [{"type": "EMAIL", "value": "nope@x.com"}])
    assert r.redacted_text == "plain text"
    assert r.mapping == {}
