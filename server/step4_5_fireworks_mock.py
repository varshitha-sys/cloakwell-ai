"""
Temporary mock for the Fireworks call, used until real API credits arrive.
This lets you test the FULL pipeline (detect -> redact -> "call" -> restore)
without needing a real API key.

Once you have Fireworks credits: just switch the import in main.py from
`from step4_5_fireworks_mock import redact_ask_restore`
back to
`from step4_5_fireworks_roundtrip import redact_ask_restore`
— nothing else needs to change, since the function signature is identical.
"""
from step2_detect_entities import detect_entities
from redact import redact, unredact


def call_fireworks_mock(prompt: str) -> str:
    """
    Fakes what a cloud model would return, so we can test the pipeline
    without a real API key. Just echoes back an acknowledgement that
    mentions the placeholders it received, so you can visually confirm
    only placeholders were "sent."
    """
    return (
        f"[MOCK RESPONSE] I received a redacted prompt and would normally "
        f"answer it here. Here's what I was given: {prompt}"
    )


def redact_ask_restore(original_text: str) -> dict:
    entities = detect_entities(original_text)
    redacted_text, lookup_table = redact(original_text, entities)

    print("Redacted text that WOULD be sent to Fireworks:")
    print(redacted_text)

    mock_response = call_fireworks_mock(redacted_text)

    print("\nMock 'Fireworks' response:")
    print(mock_response)

    restored_response = unredact(mock_response, lookup_table)

    return {
        "original_text": original_text,
        "entities_detected": entities,
        "redacted_text": redacted_text,
        "lookup_table": lookup_table,
        "fireworks_raw_response": mock_response,
        "final_response": restored_response,
    }


if __name__ == "__main__":
    test_text = (
        "Summarise this complaint from Jane Doe, SSN 123-45-6789, "
        "about our unreleased Project Falcon delay."
    )
    result = redact_ask_restore(test_text)
    print("\n=== FINAL ANSWER (shown to employee) ===")
    print(result["final_response"])