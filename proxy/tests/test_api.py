"""
Tests for the thin FastAPI classify layer (proxy/api.py).

These exercise only the deterministic Tier-1 paths so no network/LLM is involved;
Tier 2 gating is covered in test_engine.py with injected fakes.
"""
from fastapi.testclient import TestClient

import api

client = TestClient(api.app)


def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_classify_benign_is_info_tier1():
    r = client.post("/api/classify", json={"text": "hello world", "session_id": "api-benign"})
    assert r.status_code == 200
    body = r.json()
    assert body["label"] == "INFO"
    assert body["tier"] == "tier1"
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
