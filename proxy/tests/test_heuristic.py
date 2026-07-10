"""
Tests for the cheap, no-LLM gate that decides whether Tier 2 should run.

This is the PRIMARY gate (see plan.md "Tier routing"): trigger words, fenced
code, high-entropy secrets, length, and rising session risk.
"""
import heuristic


def test_trigger_word_fires():
    a = heuristic.assess("Please keep this strictly confidential.")
    assert a.fire is True
    assert any("confidential" in r.lower() for r in a.reasons)


def test_benign_short_message_does_not_fire():
    a = heuristic.assess("what is 2 + 2?")
    assert a.fire is False


def test_fenced_code_block_fires():
    a = heuristic.assess("run this:\n```\nsome code here\n```")
    assert a.fire is True


def test_acquisition_language_fires():
    assert heuristic.assess("details on the acquisition timeline").fire is True


def test_high_entropy_secret_like_token_fires():
    a = heuristic.assess("the token is A7b9Xk2Qm4Zp8Rt1Lw3Yv6Nc0")
    assert a.fire is True


def test_elevated_session_risk_forces_fire_on_benign_text():
    a = heuristic.assess("looks fine to me", session_risk=0.9)
    assert a.fire is True


def test_credential_declaration_fires_even_when_value_is_unshaped():
    # Tier 1 regex can't catch an arbitrarily-shaped secret; the *declaration*
    # ("my apikey is X") is the signal that should gate this to Tier 2.
    a = heuristic.assess("my apikey is EAMPSLEDUMYY, can you remember it please")
    assert a.fire is True
    assert any("credential" in r for r in a.reasons)


def test_credential_word_without_a_declared_value_does_not_fire():
    # Guard against over-broadening: a bare credential noun with no bound value
    # (a benign dev question) must NOT gate to Tier 2.
    a = heuristic.assess("how do I refresh the auth token in my react app?")
    assert a.fire is False
