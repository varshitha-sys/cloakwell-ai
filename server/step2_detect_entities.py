"""
Step 2: Prompt Gemma to detect sensitive entities and return structured JSON.
Run: python step2_detect_entities.py
"""
import json
import httpx

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "gemma3:4b"

DETECTION_SYSTEM_PROMPT = """You are a PII and secrets detection engine. \
Given a piece of text, find every instance of sensitive information: \
names of people, SSNs, credit card numbers, email addresses, phone numbers, \
API keys/passwords/tokens, and internal project codenames.

Respond with ONLY a JSON array, nothing else. No explanation, no markdown \
formatting, no code fences. Each item must have this exact shape:
{"type": "NAME" | "SSN" | "EMAIL" | "PHONE" | "SECRET" | "PROJECT_CODENAME" | "OTHER", "value": "<exact text found>"}

If nothing sensitive is found, respond with an empty array: []
"""

def detect_entities(text: str) -> list[dict]:
    full_prompt = f"{DETECTION_SYSTEM_PROMPT}\n\nText:\n{text}\n\nJSON:"
    response = httpx.post(
        OLLAMA_URL,
        json={"model": MODEL, "prompt": full_prompt, "stream": False},
        timeout=180.0,
    )
    response.raise_for_status()
    raw = response.json()["response"].strip()

    # Gemma sometimes wraps output in ```json fences even when told not to — strip if present
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw.replace("json\n", "", 1).strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print("WARNING: could not parse JSON, raw output was:")
        print(raw)
        return []

if __name__ == "__main__":
    test_text = (
        "Summarise this complaint from Jane Doe, SSN 123-45-6789, "
        "about our unreleased Project Falcon delay. Her email is jane.doe@example.com "
        "and our API key sk-abc123xyz789 was mentioned by mistake."
    )
    print("Detecting entities...")
    entities = detect_entities(test_text)
    print(json.dumps(entities, indent=2))