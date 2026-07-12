# Cloakwell AI — Local-First AI Redaction & Safety Layer

**AMD Developer Hackathon: ACT II — Track 3 (Unicorn Track)**

[![Gitleaks Scan](https://github.com/varshitha-sys/cloakwell-ai/actions/workflows/gitleaks.yml/badge.svg)](https://github.com/varshitha-sys/cloakwell-ai/actions/workflows/gitleaks.yml)

## 🌟 What this is

**Cloakwell AI** is a local-first security "firewall" that sits between employees and public cloud AI tools (such as ChatGPT, Claude, and Gemini). 

Whenever an employee submits a prompt containing sensitive data (corporate secrets, passwords, database credentials, SSNs, Aadhaar, or PAN cards), Cloakwell AI **intercepts and blocks** the request from leaving the local network. The query is then securely processed and answered locally by **Google Gemma 2 (2B) running on a private AMD Instinct GPU**, ensuring **zero data egress** for sensitive information. 

Clean prompts contain no PII and are transparently routed to public cloud models (DeepSeek-V4-Pro on Fireworks AI) for maximum performance.

---

## 🏗️ Architecture & Data Flow


```text
=========================================================================================
                                CLOAKWELL DYNAMIC PIPELINE
=========================================================================================

 [1. INTERCEPT]  -->   User submits a prompt on ChatGPT / Claude / Gemini webpage
                       * Intercepted in the browser before transmission
                             |
                             v
 [2. EVALUATE]   -->   Local FastAPI Proxy runs dual-tier classification check
                             |
                             +------> If Benign (INFO) --------------> [ PUBLIC CLOUD ROUTE ]
                             |                                         * Sent to Fireworks
                             |                                         * Queries DeepSeek
                             |                                                |
                             +------> If Sensitive (PII / Secrets) -> [ SECURE LOCAL ROUTE ]
                             |                                         * Zero Cloud Egress
                             |                                         * Tunneled via Serveo
                             |                                                |
                             |                                                v
                             |                                        +---------------+
                             |                                        | AMD GPU VM    |
                             |                                        | Gemma 2 (2B)  |
                             |                                        +-------+-------+
                             |                                                |
                             v                                                v
 [3. RESPONSE]   -->   Final response (Cloud or private local GPU) rendered in User UI
=========================================================================================
```

---



## 🛠️ Tech Stack

* **Google Gemma 2 (2B)** — served locally on dedicated AMD hardware for compliance classification.
* **AMD Instinct GPU / ROCm** — hardware hosting the private, local-first inference.
* **DeepSeek-V4-Pro (via Fireworks)** — cloud model for benign prompts.
* **FastAPI (Python)** — local routing server and heuristic classifier engine.
* **Vanilla HTML, CSS, JavaScript** — browser extension overlay interface.

---

## 📊 Local & Hosted Dashboard

Cloakwell AI includes a web-based dashboard to monitor redact/block statistics and view a live transaction log of data evaluation:

* **Local Mode:** When the FastAPI proxy runs, visit `http://localhost:8000/` to access the dashboard locally (served directly by the backend).
* **Hosted Mode (Render/Vercel):** Because the dashboard is built with pure static assets, it can be hosted independently on a cloud platform (like Render or Vercel). 
  * *How it works:* The hosted dashboard includes a dynamic router that automatically tunnels requests to your local background service running at `http://localhost:8000` via CORS. This allows judges to inspect the web dashboard live while it monitors their local background proxy.

---

## 🖥️ Using Cloakwell with Claude Code (and other CLI/agentic tools)

The browser extension isn't the only front door — Cloakwell also ships a
`mitmproxy` addon (`proxy/addon.py`) that TLS-intercepts outbound requests from
CLI/agentic AI tools (Claude Code, Antigravity, etc.) and runs them through the
**same** classify → redact → block pipeline (`engine.classify`) used by the
extension, in-process, with no extra HTTP hop.

**Start the proxy:**

```bash
./setup.sh
```

This launches the addon in the background and writes `.cloakwell-env.sh` with
the env vars needed to route traffic through it.

**Point Claude Code at it, in the same shell you'll launch `claude` from:**

```bash
source .cloakwell-env.sh
claude
```

`NODE_EXTRA_CA_CERTS` is required alongside `HTTPS_PROXY` — Node's TLS layer
rejects the proxy's self-signed CA without it, and Claude Code fails silently
if it's missing. `setup.sh` sets up both for you.

Every prompt now gets classified before it leaves your machine:
- `INFO` / `WARN` → forwarded untouched
- `ACTION_NEEDED` → the request body is rewritten with redacted placeholders before forwarding
- `BLOCK` → short-circuited locally; nothing leaves the host

**When you're done:**

```bash
./setup.sh stop
unset HTTPS_PROXY HTTP_PROXY NODE_EXTRA_CA_CERTS
```

Don't leave a shell's traffic routed through a proxy you've stopped.

---

## 📄 License

MIT — see [LICENSE](LICENSE).