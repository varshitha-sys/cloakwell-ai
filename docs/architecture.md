# Architecture

## Core principle

The redaction model (Gemma) and the swap/un-swap logic run **inside the customer's own trust boundary** — on their own AMD GPU, whether that's on-prem hardware or a private cloud tenant they control. No new third party ever sees raw sensitive data. The only thing that ever crosses the network boundary to Fireworks (or any other cloud AI provider) is the *redacted* version of the prompt.

## Data flow

```
┌─────────────────────────────────────────────────────────────┐
│  CUSTOMER'S TRUST BOUNDARY                                    │
│  (their hardware / their private cloud tenant — not ours,     │
│  not Fireworks')                                              │
│                                                                 │
│   1. Employee types a prompt into browser extension            │
│              │                                                 │
│              ▼                                                 │
│   2. Sent to local redaction server (localhost / internal)     │
│              │                                                 │
│              ▼                                                 │
│   3. Gemma detects sensitive entities (names, SSNs, API keys,  │
│      project codenames, etc.) — returns structured JSON        │
│              │                                                 │
│              ▼                                                 │
│   4. Server swaps real values → placeholders                   │
│      ("Jane Doe" → "[NAME_1]"), stores mapping in memory        │
│              │                                                 │
└──────────────┼─────────────────────────────────────────────────┘
               │  ONLY the redacted text crosses this line
               ▼
        ┌─────────────────────────┐
        │  Fireworks AI (or other  │
        │  cloud model) — sees     │
        │  ONLY placeholders       │
        └───────────┬─────────────┘
               │  returns response using placeholders
               ▼
┌─────────────────────────────────────────────────────────────┐
│  BACK INSIDE CUSTOMER'S TRUST BOUNDARY                         │
│                                                                 │
│   5. Server swaps placeholders back to real values using        │
│      the in-memory lookup table                                │
│              │                                                 │
│              ▼                                                 │
│   6. Employee sees the final answer with real data restored     │
└─────────────────────────────────────────────────────────────┘
```

## Components

| Component | Runs where | Responsibility |
|---|---|---|
| Browser extension | Employee's browser | Intercepts prompt before submission to ChatGPT/Claude/etc., sends to local server |
| Redaction server | Local machine / customer's AMD GPU instance | Runs Gemma detection, swap/un-swap logic, calls Fireworks |
| Gemma (detection model) | Local / AMD GPU via ROCm | Entity detection only — returns structured JSON list of sensitive spans |
| Lookup table | In-memory, scoped to request/session | Maps placeholders ↔ real values; never written to disk or sent over network |
| Fireworks AI | Cloud (third party) | Only ever receives redacted text; never sees raw sensitive data |
| Audit log (optional) | Local disk, same machine | Logs *counts/categories* of redactions (e.g. "1 SSN, 2 names") — not the actual values |

## What "local" means in two different contexts

- **Hackathon demo:** "local" = your laptop or the AMD Developer Cloud GPU instance provided for the event. This stands in for the customer's infrastructure in the real deployment.
- **Real product deployment:** "local" = the customer's own on-prem server or their own private cloud tenant (their AWS/Azure/OCI account, their AMD Instinct instance). The vendor (us) ships software; the customer runs it on infrastructure they control. We never host or see customer data at any point.

## Key design decisions

1. **Reversible placeholder swap, not deletion.** Deleting sensitive data outright would break the usefulness of the prompt. Swapping to placeholders preserves sentence structure so the cloud model can still do its job, then the real values are restored locally before the employee sees the answer.
2. **In-memory only lookup table.** No persistence by default — the mapping exists only for the lifetime of a single request/session, then is discarded. This is the simplest and safest option for a hackathon demo; persistence (if ever needed) would be local-disk-only, never remote.
3. **Structured JSON output from Gemma.** Rather than free-text detection, Gemma is prompted to return a structured list of entities (type + span), which is what the swap logic actually needs — this also makes detection quality easier to evaluate and debug.
4. **AMD GPU as the trust boundary, not just a compute choice.** Running the detection model on AMD infrastructure the customer controls (via ROCm) is the actual product claim, not incidental — it's what makes "the redactor never leaves your building" true rather than aspirational.

## Related docs

- [`build-plan.md`](build-plan.md) — detailed research, technical comparisons, and day-by-day build plan
- [`pitch-notes.md`](pitch-notes.md) — pitch framing, competitive positioning vs. Nightfall AI, demo script