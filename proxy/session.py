"""
Conversation-level running risk score (minimal, but real — not faked).

A single message can look benign while a *thread* trends sensitive. This tracker
keeps a per-session leaky-accumulator score so cumulative context can raise the
effective risk (and thus the Tier 2 gate / final label) over a conversation.

This is the deliberately-minimal version for the classification core; Day-2
Task 10 deepens the scoring. State is in-memory only (never persisted), scoped to
the process, keyed by an opaque session id.

Public API:
    tracker = SessionTracker()
    tracker.update(session_id, message_risk) -> float   # new running risk 0..1
    tracker.risk(session_id) -> float                    # current running risk 0..1
"""
from __future__ import annotations

# Leaky accumulator: old score decays a little each turn, the new message's risk
# is added in. Sensitive turns compound; benign turns let it settle back down.
_DECAY = 0.9
_GAIN = 0.5


class SessionTracker:
    def __init__(self) -> None:
        self._scores: dict[str, float] = {}

    def risk(self, session_id: str) -> float:
        return self._scores.get(session_id, 0.0)

    def update(self, session_id: str, message_risk: float) -> float:
        message_risk = max(0.0, min(1.0, message_risk))
        current = self._scores.get(session_id, 0.0)
        new_score = min(1.0, current * _DECAY + message_risk * _GAIN)
        self._scores[session_id] = new_score
        return new_score
