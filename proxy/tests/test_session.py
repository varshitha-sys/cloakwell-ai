"""Tests for the minimal conversation-level running risk tracker."""
import session


def test_new_session_starts_at_zero():
    t = session.SessionTracker()
    assert t.risk("s1") == 0.0


def test_risk_rises_as_sensitive_messages_accumulate():
    t = session.SessionTracker()
    r1 = t.update("s1", 0.8)
    r2 = t.update("s1", 0.8)
    assert 0.0 < r1 <= r2 <= 1.0


def test_sessions_are_isolated():
    t = session.SessionTracker()
    t.update("s1", 0.9)
    assert t.risk("s2") == 0.0


def test_risk_is_capped_at_one():
    t = session.SessionTracker()
    r = 0.0
    for _ in range(25):
        r = t.update("s1", 1.0)
    assert r == 1.0


def test_benign_message_keeps_risk_at_zero():
    t = session.SessionTracker()
    assert t.update("s1", 0.0) == 0.0
