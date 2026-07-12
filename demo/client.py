"""
Self-contained demo client for the Cloakwell DLP proxy (docker-compose.yml).

Fires a curated set of prompts -- covering every verdict -- at api.anthropic.com
THROUGH the mitmproxy addon, so a judge can watch the dashboard populate with
BLOCK / REDACT / forward decisions with no API key.

Why no key is needed: the addon classifies and logs each prompt BEFORE forwarding
(engine.classify -> logger.log_transaction). BLOCK prompts are short-circuited
locally (403, nothing leaves). Benign prompts are forwarded and simply 401 at
Anthropic -- harmless, since the verdict was already recorded. Works offline too:
a forwarded prompt that can't reach Anthropic still got logged first.
"""
from __future__ import annotations

import os
import sys
import time

import httpx

PROXY = os.getenv("PROXY_URL", "http://proxy:8443")
CA = os.getenv("REQUESTS_CA_BUNDLE", "/certs/mitmproxy-ca-cert.pem")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"

# (kind, prompt) — one per verdict class so every dashboard bucket lights up.
PROMPTS = [
    ("secret",   "Here is my AWS key AKIAIOSFODNN7EXAMPLE, can you validate it?"),
    ("secret",   "Log me into the box with password=hunter2 please."),
    ("national", "My SSN is 123-45-6789, help me file my taxes."),
    ("card",     "Charge my card 4242 4242 4242 4242 for the subscription."),
    ("phone",    "Call me back on +91 98765 43210 about the delivery."),
    ("email",    "Send the invoice to jane.doe@example.com when ready."),
    ("benign",   "Refactor this Python function to run faster."),
    ("benign",   "Summarize the plot of Hamlet in two sentences."),
]


def wait_for_cert(timeout_s: int = 60) -> bool:
    """Block until the proxy's CA cert appears on the shared volume."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if os.path.exists(CA):
            return True
        time.sleep(0.5)
    return False


def send(client: httpx.Client, text: str):
    """POST one Anthropic-messages-shaped body; return the status (or error name)."""
    body = {
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 64,
        "messages": [{"role": "user", "content": text}],
    }
    try:
        resp = client.post(ANTHROPIC_URL, json=body, timeout=20)
        return resp.status_code
    except Exception as exc:  # no upstream connectivity -> verdict was still logged
        return type(exc).__name__


def main() -> int:
    if not wait_for_cert():
        print(f"[client] CA cert never appeared at {CA}", file=sys.stderr)
        return 1
    # Small settle so the mitmdump listener is accepting connections.
    time.sleep(2)

    print(f"[client] routing {len(PROMPTS)} prompts through {PROXY}\n")
    # verify=CA makes the client trust mitmproxy's intercepted cert; the proxy is
    # picked up from HTTPS_PROXY (trust_env) and PROXY_URL below (explicit).
    with httpx.Client(proxy=PROXY, verify=CA) as client:
        for kind, text in PROMPTS:
            status = send(client, text)
            verdict = (
                "BLOCKED by DLP" if status == 403
                else f"forwarded (upstream={status})"
            )
            print(f"[client] {kind:9} -> {verdict}")

    print("\n[client] done. Open http://localhost:8000 to see the audit log + stats.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
