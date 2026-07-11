# CloakWell — Local-First AI Redaction & Safety Layer

**AMD Developer Hackathon: ACT II — Track 3 (Unicorn Track)**

[![Gitleaks Scan](https://github.com/varshitha-sys/cloakwell-ai/actions/workflows/gitleaks.yml/badge.svg)](https://github.com/varshitha-sys/cloakwell-ai/actions/workflows/gitleaks.yml)

## 🌟 What this is

**CloakWell** is a local-first security "firewall" that sits between employees and public cloud AI tools (such as ChatGPT, Claude, and Gemini). 

Whenever an employee submits a prompt containing sensitive data (corporate secrets, passwords, database credentials, SSNs, Aadhaar, or PAN cards), CloakWell **intercepts and blocks** the request from leaving the local network. The query is then securely processed and answered locally by **Google Gemma 2 (2B) running on a private AMD Instinct GPU**, ensuring **zero data egress** for sensitive information. 

Clean prompts contain no PII and are transparently routed to public cloud models (DeepSeek-V4-Pro on Fireworks AI) for maximum performance.

---

## 🏗️ Architecture & Data Flow

For the full network topology and setup guide, see [AMD_GEMMA_INTEGRATION.md](AMD_GEMMA_INTEGRATION.md).

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

## 📄 License

MIT — see [LICENSE](LICENSE).