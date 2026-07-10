"""
Tests for the thin FastAPI classify layer (proxy/api.py).

Tier 2 now runs by default (only an already-BLOCK Tier 1 verdict skips it), so we
stub Gemma at the client boundary to keep these offline and deterministic. Tier 2
gating/behaviour is covered in test_engine.py with injected fakes.
"""
import json

import pytest
from fastapi.testclient import TestClient

import api
import tier2

client = TestClient(api.app)


@pytest.fixture(autouse=True)
def stub_gemma(monkeypatch):
    """Default-on Tier 2 would otherwise hit the network; return a benign INFO."""
    monkeypatch.setattr(
        tier2,
        "_fireworks_client",
        lambda messages: json.dumps(
            {"label": "INFO", "confidence": 0.9, "reasoning": "stub", "entities": []}
        ),
    )


def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_classify_benign_is_info_via_tier2():
    r = client.post("/api/classify", json={"text": "hello world", "session_id": "api-benign"})
    assert r.status_code == 200
    body = r.json()
    assert body["label"] == "INFO"
    assert body["tier"] == "tier2"   # default-on: Gemma consulted, agrees it's benign
    assert "redacted_text" in body and "session_risk" in body


def test_classify_secret_blocks_and_redacts():
    r = client.post(
        "/api/classify",
        json={"text": "the key is sk-abc123xyz789def456ghi", "session_id": "api-secret"},
    )
    body = r.json()
    assert body["label"] == "BLOCK"
    assert "sk-abc123xyz789def456ghi" not in body["redacted_text"]
    assert any(e["type"] == "API_KEY" for e in body["entities"])


def test_classify_missing_text_is_422():
    r = client.post("/api/classify", json={"session_id": "api-x"})
    assert r.status_code == 422


def test_classify_accepts_source_and_context():
    r = client.post(
        "/api/classify",
        json={
            "text": "just a normal question",
            "source": "extension",
            "session_id": "api-ctx",
            "context": ["earlier message in the thread"],
        },
    )
    assert r.status_code == 200
    assert r.json()["source"] == "extension"
