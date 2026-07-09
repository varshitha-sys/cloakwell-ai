"""
Step 3: Swap detected entities for placeholders, and swap them back later.
This is the core module — imported by later steps, not run directly.
"""


def redact(text: str, entities: list[dict]) -> tuple[str, dict]:
    """
    Replace each entity's real value with a placeholder like [NAME_1].
    Returns (redacted_text, lookup_table) where lookup_table maps
    placeholder -> real value, so it can be reversed later.
    """
    redacted_text = text
    lookup_table = {}
    type_counters: dict[str, int] = {}

    # Sort by length descending so longer matches (e.g. full names) get
    # replaced before any shorter substrings that might overlap.
    sorted_entities = sorted(entities, key=lambda e: len(e.get("value", "")), reverse=True)

    for entity in sorted_entities:
        value = entity.get("value")
        etype = entity.get("type", "OTHER")
        if not value or value not in redacted_text:
            continue

        type_counters[etype] = type_counters.get(etype, 0) + 1
        placeholder = f"[{etype}_{type_counters[etype]}]"

        redacted_text = redacted_text.replace(value, placeholder)
        lookup_table[placeholder] = value

    return redacted_text, lookup_table


def unredact(text: str, lookup_table: dict) -> str:
    """
    Replace placeholders back with their real values.
    """
    restored = text
    for placeholder, real_value in lookup_table.items():
        restored = restored.replace(placeholder, real_value)
    return restored


if __name__ == "__main__":
    # Quick manual test
    sample_text = "Contact Jane Doe at jane.doe@example.com about Project Falcon."
    sample_entities = [
        {"type": "NAME", "value": "Jane Doe"},
        {"type": "EMAIL", "value": "jane.doe@example.com"},
        {"type": "PROJECT_CODENAME", "value": "Project Falcon"},
    ]

    redacted, lookup = redact(sample_text, sample_entities)
    print("Redacted:", redacted)
    print("Lookup table:", lookup)

    restored = unredact(redacted, lookup)
    print("Restored:", restored)
    assert restored == sample_text, "Round-trip failed!"
    print("Round-trip OK.")