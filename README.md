# [Project Name TBD] — Local-First AI Redaction Layer

**AMD Developer Hackathon: ACT II — Track 3 (Unicorn Track)**

## What this is

A local-first "firewall" that sits between employees and cloud AI tools (ChatGPT, Fireworks-hosted models, Gemini, etc.). Sensitive data — PII, PCI, PHI, credentials/secrets — is detected and redacted **before** any request leaves the user's own infrastructure, using a small open-source model (Gemma) running on an AMD GPU. The cloud model only ever sees generic placeholders; the real values are swapped back in locally once the response returns.

Unlike existing AI DLP products (e.g. Nightfall), which route your data through *their* cloud to scrub it, this runs entirely inside the customer's own trust boundary — no new third party ever sees raw data.

## Why this matters

Companies want employees using AI tools, but security teams block it because there's no guarantee sensitive data won't leak into a prompt. Current solutions either ban AI outright or add another cloud vendor into the data path. This removes that tradeoff.

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the full data-flow diagram and trust-boundary breakdown.

**Summary:** Employee prompt → local detection (Gemma, on AMD GPU) → sensitive spans swapped for placeholders → redacted prompt sent to Fireworks/cloud model → response returned → placeholders swapped back locally → employee sees a normal answer. Nothing sensitive ever crosses the network boundary.

## Status

🚧 Actively being built during the hackathon (July 6–11, 2026). This README will be updated as components land.

## Setup & Usage

> Coming soon — this section will contain exact steps to run the project locally, once the server component is functional.

```bash
# placeholder — will be replaced with real instructions
git clone <repo-url>
cd <repo-name>
docker compose up
```

## Repo structure

```
.
├── server/          # Core redaction engine: detect → swap → call → un-swap
├── extension/        # Browser extension for real-time prompt interception (demo surface)
├── docs/             # Architecture notes, research, pitch materials
├── Dockerfile
└── docker-compose.yml
```

## Tech stack

- **Gemma** (via Ollama / AMD Developer Cloud) — local entity detection
- **Fireworks AI API** — cloud model calls (post-redaction only)
- **AMD GPU / ROCm** — hosts the local detection model
- Python (FastAPI) — redaction server
- Browser extension (Chrome) — interception layer

## License

MIT — see [`LICENSE`](LICENSE).