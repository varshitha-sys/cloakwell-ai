"""Tests for the Tier 1 regex PII detection engine."""
import tier1


def _types(text):
    return {e["type"] for e in tier1.detect(text)}


def _find(text, etype):
    """Return the first entity of the given type, or None."""
    return next((e for e in tier1.detect(text) if e["type"] == etype), None)


def _assert_detected(text, etype, value):
    ent = _find(text, etype)
    assert ent is not None, f"expected {etype} in {text!r}, got {tier1.detect(text)}"
    assert ent["value"] == value
    # Offsets must slice back to the exact value.
    assert text[ent["start"]:ent["end"]] == value


# --- Positive cases: right type + correct offsets -------------------------


def test_email():
    _assert_detected("ping jane.doe@example.com now", "EMAIL", "jane.doe@example.com")


def test_ssn():
    _assert_detected("SSN 123-45-6789 on file", "SSN", "123-45-6789")


def test_credit_card_valid_luhn():
    _assert_detected("card 4242 4242 4242 4242 ok", "CREDIT_CARD", "4242 4242 4242 4242")


def test_ip_address():
    _assert_detected("host 192.168.1.20 down", "IP_ADDRESS", "192.168.1.20")


def test_aadhaar_valid_verhoeff():
    # 9999 4105 7058 is a UIDAI-published, Verhoeff-valid test Aadhaar.
    _assert_detected("aadhaar 9999 4105 7058 here", "AADHAAR", "9999 4105 7058")


def test_pan():
    _assert_detected("PAN ABCDE1234F issued", "PAN", "ABCDE1234F")


def test_indian_phone():
    assert "INDIAN_PHONE" in _types("call +91 9876543210 today")
    # Real-world formatting with an internal space.
    assert "INDIAN_PHONE" in _types("call +91 98765 43210 today")


def test_aws_access_key():
    _assert_detected("key AKIAIOSFODNN7EXAMPLE set", "AWS_ACCESS_KEY", "AKIAIOSFODNN7EXAMPLE")


def test_github_token():
    tok = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"
    _assert_detected(f"token {tok} leaked", "GITHUB_TOKEN", tok)


def test_gcp_api_key():
    key = "AIza" + "B" * 35
    _assert_detected(f"gcp {key} exposed", "GCP_API_KEY", key)


def test_generic_api_key():
    _assert_detected("use sk-abc123xyz789def456ghi now", "API_KEY", "sk-abc123xyz789def456ghi")


def test_password():
    assert "PASSWORD" in _types("login password=hunter2 works")


def test_auth_url():
    assert "AUTH_URL" in _types("get https://api.example.com/d?api_key=SECRET123 fast")


# --- Negative cases: checksums / validators reject near-misses ------------


def test_invalid_luhn_not_a_card():
    # 16 digits but fails Luhn -> must NOT be flagged as a credit card.
    assert "CREDIT_CARD" not in _types("number 1234 5678 9012 3456 here")


def test_invalid_verhoeff_not_aadhaar():
    # 12 digits, invalid Verhoeff check -> not Aadhaar.
    assert "AADHAAR" not in _types("digits 1234 5678 9012 there")


def test_invalid_ip_octets():
    assert "IP_ADDRESS" not in _types("version 999.999.999.999 build")


def test_bare_word_password():
    assert "PASSWORD" not in _types("I forgot my password again")


# --- Integration ----------------------------------------------------------


def test_canonical_string():
    text = (
        "Summarise this complaint from Jane Doe, SSN 123-45-6789, about our "
        "unreleased Project Falcon delay. Her email is jane.doe@example.com and "
        "our API key sk-abc123xyz789def456ghi was mentioned by mistake."
    )
    assert {"SSN", "EMAIL", "API_KEY"} <= _types(text)
