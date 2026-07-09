"""
mitmproxy addon: intercept CLI-tool AI traffic -> detect -> act, all in-process.

This is the Day-1 spike (spike/dlp_addon.py) grown up: instead of a canary
string-replace, it runs the real classification core (engine.classify) on the
decrypted outbound prompt and acts on the verdict:

    INFO / WARN    -> forward untouched (logged)
    ACTION_NEEDED  -> rewrite the request body with redacted text, then forward
    BLOCK          -> short-circuit with an error response; nothing leaves the host

engine.classify runs in THIS process (no HTTP hop back to api.py), so the proxy
and the /classify API share one detection pipeline.

Run:  .venv/bin/mitmdump -s addon.py --listen-port 8443
(point Claude Code at it with HTTPS_PROXY + NODE_EXTRA_CA_CERTS — see spike/README.md)
"""
from __future__ import annotations

import copy
import json

import engine

try:  # only present when actually running under mitmproxy
    from mitmproxy import http
except ImportError:  # keeps the pure helpers importable/testable standalone
    http = None

# AI API hosts whose request bodies we inspect.
AI_HOSTS = {
    "api.anthropic.com",
    "generativelanguage.googleapis.com",
    "api.openai.com",
    "api.fireworks.ai",
}

_ACTION_BY_LABEL = {
    "INFO": "forward",
    "WARN": "forward",
    "ACTION_NEEDED": "redact",
    "BLOCK": "block",
}


# --- Pure helpers (mitmproxy-free, unit-tested) ---------------------------


def _text_from_content(content) -> str:
    """Anthropic/OpenAI message content is a string or a list of typed blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
        return "\n".join(p for p in parts if p)
    return ""


def extract_prompt(body: dict) -> str:
    """Pull the latest user message text out of a chat-completions-style body."""
    for msg in reversed(body.get("messages", []) or []):
        if msg.get("role") == "user":
            return _text_from_content(msg.get("content", ""))
    return ""


def apply_redaction(body: dict, redacted_text: str) -> dict:
    """Return a copy of ``body`` with the last user message replaced by redacted text."""
    new_body = copy.deepcopy(body)
    for msg in reversed(new_body.get("messages", []) or []):
        if msg.get("role") == "user":
            msg["content"] = redacted_text
            break
    return new_body


def decide(result: dict) -> str:
    """Map a classification label to a proxy action."""
    return _ACTION_BY_LABEL.get(result.get("label", "INFO"), "forward")


def _block_body(result: dict) -> str:
    """An API-error-shaped payload so the CLI tool surfaces a clear message."""
    entities = ", ".join(sorted({e.get("type", "") for e in result.get("entities", [])}))
    return json.dumps(
        {
            "type": "error",
            "error": {
                "type": "dlp_blocked",
                "message": f"Blocked by local DLP: sensitive data detected ({entities or 'policy violation'}).",
            },
        }
    )

# --- mitmproxy hook -------------------------------------------------------

class DLPAddon:
    def request(self, flow) -> None:
        if flow.request.pretty_host not in AI_HOSTS:
            return
        try:
            body = json.loads(flow.request.get_text())
        except (ValueError, TypeError):
            return  # non-JSON body: nothing structured to inspect

        prompt = extract_prompt(body)
        if not prompt.strip():
            return

        session_id = getattr(getattr(flow, "client_conn", None), "id", "proxy")
        result = engine.classify(prompt, session_id=str(session_id), source="proxy")
        action = decide(result)

        label = result["label"]
        print(f"[DLP] {flow.request.pretty_host} label={label} action={action} \n tier={result['tier']} session_risk={result['session_risk']:.2f}")

        if action == "block":
            flow.response = http.Response.make(
                403, _block_body(result), {"Content-Type": "application/json"}
            )
        elif action == "redact":
            flow.request.set_text(json.dumps(apply_redaction(body, result["redacted_text"])))


addons = [DLPAddon()]
