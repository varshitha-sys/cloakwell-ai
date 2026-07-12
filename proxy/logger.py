"""
SQLite Audit Logger for CLOAKWELL.

Maintains a secure, local-only database containing logs of intercepted queries.
To preserve the 'local-first privacy' promise, this logger:
1. Hashes the original prompt (SHA-256) instead of saving the raw text.
2. Saves the redacted text (which contains only placeholders).
3. Sanitizes entity metadata by removing raw values and storing only type/offset.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path

# Default: alongside the code (unchanged for setup.sh / local runs). Containers
# override this to a shared volume so the proxy (writer) and dashboard (reader)
# see the same DB — see docker-compose.yml.
DB_PATH = Path(
    os.getenv("CLOAKWELL_DB_PATH", str(Path(__file__).resolve().parent / "cloakwell_audit.db"))
)


def get_db_connection() -> sqlite3.Connection:
    """Create a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the audit logs table if it does not already exist."""
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                source TEXT NOT NULL,
                original_text_hash TEXT NOT NULL,
                redacted_text TEXT NOT NULL,
                entities TEXT NOT NULL,  -- JSON list of sanitized entities
                label TEXT NOT NULL,
                action TEXT NOT NULL
            )
        """)
        conn.commit()


def log_transaction(
    source: str,
    original_text: str,
    redacted_text: str,
    entities: list[dict],
    label: str,
    action: str,
) -> int:
    """
    Log an intercepted transaction to the SQLite database.
    Ensures no raw PII is written to disk.
    """
    # 1. Compute SHA-256 hash of raw input
    raw_hash = hashlib.sha256(original_text.encode("utf-8")).hexdigest()

    # 2. Sanitize entities to remove raw text values (keep only type and spans)
    sanitized_entities = []
    for ent in entities:
        sanitized_entities.append({
            "type": ent.get("type", "SENSITIVE"),
            "start": ent.get("start"),
            "end": ent.get("end")
        })
    entities_json = json.dumps(sanitized_entities)

    # 3. Write securely to database
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO audit_logs (source, original_text_hash, redacted_text, entities, label, action)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (source, raw_hash, redacted_text, entities_json, label, action)
        )
        conn.commit()
        return cursor.lastrowid


def get_logs(limit: int = 50, offset: int = 0, label_filter: str | None = None) -> list[dict]:
    """Retrieve audit logs, with optional label filtering and pagination."""
    query = "SELECT id, timestamp, source, original_text_hash, redacted_text, entities, label, action FROM audit_logs"
    params = []

    if label_filter:
        query += " WHERE label = ?"
        params.append(label_filter)

    query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with get_db_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        
    logs = []
    for r in rows:
        logs.append({
            "id": r["id"],
            "timestamp": r["timestamp"],
            "source": r["source"],
            "original_text_hash": r["original_text_hash"],
            "redacted_text": r["redacted_text"],
            "entities": json.loads(r["entities"]),
            "label": r["label"],
            "action": r["action"],
        })
    return logs


def get_stats() -> dict:
    """Calculate aggregate counts for the dashboard cards and charts."""
    with get_db_connection() as conn:
        # Total counts
        total = conn.execute("SELECT COUNT(*) as count FROM audit_logs").fetchone()["count"]
        
        # Label breakdown
        label_rows = conn.execute("SELECT label, COUNT(*) as count FROM audit_logs GROUP BY label").fetchall()
        by_label = {r["label"]: r["count"] for r in label_rows}
        for lbl in ("INFO", "WARN", "ACTION_NEEDED", "BLOCK"):
            if lbl not in by_label:
                by_label[lbl] = 0

        # Action breakdown
        action_rows = conn.execute("SELECT action, COUNT(*) as count FROM audit_logs GROUP BY action").fetchall()
        by_action = {r["action"]: r["count"] for r in action_rows}
        for act in ("forward", "redact", "block"):
            if act not in by_action:
                by_action[act] = 0
                
    return {
        "total": total,
        "by_label": by_label,
        "by_action": by_action
    }
