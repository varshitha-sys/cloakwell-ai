# Building a Nightfall-Style "LLM Firewall" for the AMD Developer Hackathon: ACT II — Implementation Plan

## TL;DR
- **Build an "AI DLP prompt firewall" for the Unicorn Track (Track 3):** a two-stage detection pipeline where a fast open-source PII/NER model (GLiNER-PII or Piiranha) runs on an AMD Instinct MI300X on AMD Developer Cloud for first-pass span detection, and a Fireworks AI LLM (Llama/Qwen/GLM/Gemma with JSON mode) does contextual classification, risk scoring, and redaction reasoning — enforced through a policy engine (block / redact / warn) with an audit-log dashboard.
- **Interception should be a browser extension for the demo (visually intercepting chatgpt.com/claude.ai) backed by an OpenAI-compatible proxy** modeled on LiteLLM's Presidio guardrail pattern, so you demonstrate both the "shadow AI" employee use case and the developer/API use case.
- **This maps directly to the four published Unicorn Track judging criteria** (Creativity/Originality, Product/Market Potential, Completeness, Use of AMD Platforms). Lean into "Use of AMD Platforms" by hosting your detector model on MI300X via vLLM, and chase the extra **$2,000 "Best AMD-Hosted Gemma Project"** bonus by running Google's Gemma as your AMD-hosted reasoning model.

## Key Findings

### The hackathon context
- **AMD Developer Hackathon: ACT II** runs **July 6–11, 2026**, online, organized by lablab.ai with AMD and NativelyAI. Submission deadline is **July 11, 2026, 15:00 UTC**.
- **Three tracks.** Your project fits **Track 3 — the "Unicorn Track" (all levels)**, described as: "Use any open-source models and frameworks alongside AMD GPUs and/or Fireworks AI API credits to build a product- or startup-oriented project." Track 3 is **judge-evaluated** (Tracks 1 and 2 are leaderboard-ranked).
- **Unicorn Track judging criteria** (no numeric weights published): **Creativity and Originality**, **Product/Market Potential**, **Completeness**, and **Use of AMD Platforms** ("How meaningfully AMD infrastructure is incorporated into the project"). The organizers explicitly say: "Think startup pitch, not benchmark run" and "Submissions are not scored on speed, token usage, or accuracy."
- **Submission requirements:** project submitted via lablab.ai before deadline; **all submissions must be containerized**; **public GitHub repo with a README** containing setup/usage; app must be runnable from the instructions; a **Video Presentation and Slide Presentation are required** (plus title, short/long description, tags, cover image, demo app URL); submissions must be original and MIT-compliant. No max demo-video length is specified for Track 3.
- **Prizes:** each track awards **$2,500 / $1,500 / $1,000** (1st/2nd/3rd); total pool **$21,000**. **Additional $6,000 Gemma bonus pool** including **"Track 3 Best AMD-Hosted Gemma Project — $2,000."**
- **Credits:** all participants get **$50 in Fireworks AI API credits**; new AMD AI Developer Program members get **$100 AMD Developer Cloud + $50 Fireworks** via a separate application. AMD.com states: "AMD is offering an initial $100 complimentary cloud credit to qualified developers who apply and join AMD AI Developer Program," with credits arriving "within 3 business days" and expiring 30 days from deposit.
- **Team size:** no explicit numeric cap is published for this event; solo through small teams are clearly allowed, so a 5-person team is fine.
- **Note on conflicting figures:** a third-party aggregator lists a "$10,000 pool ($5,000/$3,000/$2,000)" — that is outdated; trust the official lablab.ai figures ($21,000 total, $2,500/$1,500/$1,000 per track).

### How Nightfall's "Firewall for AI" actually works (your reference model)
- **Launched May 22, 2024** — Nightfall's press release headline: "Nightfall Launches Firewall for AI to Secure GPT-4o," quoting CTO Rohan Sathe. Nightfall describes it as a **"client wrapper"** that protects interactions with GenAI apps and pipelines — it is **API-driven and agentless**, integrating via APIs/SDKs rather than sitting inline as a network reverse proxy. Nightfall explicitly recommends an **"API-centric approach"** over inline reverse-proxy interception to avoid latency.
- **Detection is ML-based, not regex.** Nightfall documentation states it can "programmatically scan text and file inputs using 150+ detectors," spanning **PII, PCI, PHI, and secrets/credentials**, plus image and file classifiers. Per SC Media's 2024 SC Awards coverage, Nightfall's engine is "Built with over 100 million parameters," powered by AI/NLP with "85% more accuracy than traditional regex-based tools." PII/PCI use a **CNN with LLM-generated embeddings** for context; PHI uses a transformer that maps health data to individuals; secrets use a fine-tuned model. Per nightfall.ai/firewall-for-ai, they claim: "≥95% precision/recall • ≥99.9% request success rate • ≥1k RPS peak throughput • ≤100ms P99 latency, for 4 or a more detectors."
- **Detector examples:** PII (name, DOB, address, email, phone, **SSN**, driver's license, VIN, ITIN), PHI (ICD10, NPI, MBI), Secrets (API key, DB connection string, password), Images (passport, driver's license, credit card, SSN card).
- **Policy actions:** Nightfall frames actions as **blocking, redaction, quarantine, deletion, or warning/coaching**. For LLM prompts the sensible defaults are **"redact and allow" for medium risk** and **"block and route to review" for high risk (PHI, full payment data)**.
- **Deployment forms:** (1) the **Developer Platform** (REST API + SDKs in Python/Java/Node/Go, scan text/files, webhook callback with JSON findings, confidence levels LIKELY/VERY_LIKELY, character offsets), and (2) a **lightweight browser extension** ("Firewall for AI Copilots") that "secures ChatGPT, Gemini, Claude, and more in minutes" and sanitizes/blocks prompts with in-app coaching, deployable via Google Workspace/MDM.
- **Takeaway for your build:** copy the architecture pattern (detect → score → policy action → audit), copy the detector taxonomy (PII/PCI/PHI/secrets), and copy the two-surface strategy (browser extension for humans + API/proxy for apps). You will substitute open-source detectors + Fireworks LLMs for Nightfall's proprietary models.

### PII detection approaches — comparison and recommendation
Three families, in increasing order of context-awareness and latency:

1. **Regex / pattern matching + checksums.** Fast, deterministic, auditable. Great for **structured** PII: emails, credit cards (Luhn checksum), SSNs, phone numbers, API keys, JWTs, private keys, `.env`/config content. Weakness: no context; misses names/addresses; high false positives on lookalikes (test cards, sample keys). This is your cheap first filter.
2. **NER / transformer models (the sweet spot for a hackathon):**
   - **Microsoft Presidio** — open-source orchestration framework combining regex recognizers + spaCy/HF NER + checksum validation + context-word confidence boosting + a separate Anonymizer (redact/replace/mask/hash/encrypt). Ships recognizers for EMAIL_ADDRESS, US_SSN, CREDIT_CARD, PHONE_NUMBER, etc. Deployable as two containers (Analyzer on :5002, Anonymizer on :5001). It is the de-facto integration standard (LiteLLM, PII Shield). Weakness: default spaCy NER struggles with non-Western names; needs container orchestration.
   - **GLiNER-PII** (urchade/GLiNER; knowledgator/gliner-pii-{edge,small,base,large}-v1.0; GLiNER2 from Fastino) — **zero-shot** bidirectional-transformer NER: you pass the entity labels you want at inference time, no retraining. ~205–209M params, runs on CPU/GPU, ONNX/quantized options. Base PII model ~**81% F1** on a broad 60-entity synthetic test. Strong on recall for IDs/dates; **notably good at Indian/Asian names** where Presidio's default fails, at ~75ms/CPU for the base model. GLiNER integrates as an external recognizer inside Presidio.
   - **Piiranha-v1** (iiiorg/piiranha-v1-detect-personal-information) — per its Hugging Face model card, a **280M-param fine-tuned mDeBERTa-v3** achieving **98.27% PII-token detection (recall), 99.44% overall classification accuracy, 98.48% precision, 99.84% specificity**, across **6 languages and 17 PII types**, with a 256-token context (chunk longer text), trained on 400,000+ masked-PII records using H100s sponsored by Akash Network. **License note: the card lists CC-BY-NC-ND-4.0 (non-commercial, no-derivatives), not MIT** — fine for a hackathon demo, but flag it if you pitch commercialization.
   - **DeBERTa fine-tuned on ai4privacy** — highest reported benchmark **F1 ≈ 0.9757** on a fixed entity set (54 classes); this is the default model inside **LLM Guard's Anonymize scanner** (Ai4Privacy DeBERTa).
   - **Reality check on benchmarks:** these headline F1s come largely from **synthetic** data (ai4privacy). Independent cross-domain benchmarks show heavy degradation on out-of-distribution text — one 2026 unified benchmark (PIIBench) found *every* off-the-shelf system scored **span-level F1 below 0.14** on heterogeneous multi-source data (best was Presidio at 0.1385), and clinical text drops GLiNER from ~0.81 to ~0.41 F1. Interpretation: **demo on clean, in-domain prompts; do not over-claim accuracy; combine regex + ML.**
3. **LLM-based detection (Fireworks).** Prompt an instruction-tuned LLM with **JSON mode / structured output / function calling** to return typed spans + risk. Highest context-awareness (catches "the patient in Room 11," implicit identifiers, business-confidential IP that NER misses), but slowest and priciest per call. Context-aware fine-tunes can hit span F1 ~0.96 (CAPID). Use it as the **second-stage adjudicator**, not the first-pass scanner.

**Recommendation:** a **cascade** — regex (instant, structured) → GLiNER-PII **or** Piiranha on the MI300X (fast, contextual spans) → Fireworks LLM adjudication **only when** the first two stages flag medium/ambiguous risk or when policy demands contextual judgment. This mirrors what practitioners recommend ("Production systems should combine regex + ML models") and keeps latency and token spend low.

### Open-source guardrail/proxy building blocks you can reuse
- **LLM Guard (Protect AI, MIT; Protect AI acquired by Palo Alto Networks in 2025)** — 15 input + 20 output scanners including **Anonymize** (uses Ai4Privacy DeBERTa + regex, a **Vault** for reversible placeholder tokens like `[REDACTED_PERSON_1]`, and a **Deanonymize** scanner to restore values in the response). This is basically a ready-made open-source "firewall for AI" core — study it or wrap it.
- **LiteLLM proxy** — OpenAI-compatible gateway (100+ providers) with a **Presidio guardrail** you configure in YAML with `mode: pre_call` and `pii_entities_config` mapping each entity to `MASK` or `BLOCK`; supports `output_parse_pii` to un-mask in responses, per-entity `presidio_score_thresholds`, and policies scoped per team/key. This is the fastest path to a working **reverse-proxy/API-gateway** demo — point any OpenAI SDK at it and PII is masked before it leaves.
- **Microsoft "PII Shield" reference** (Azure community) — a FastAPI privacy proxy implementing the **"anonymize → LLM → de-anonymize" sandwich** with Presidio, per-entity strategies (replace/hash/encrypt/fake), session IDs, custom **India-specific recognizers (Aadhaar, PAN, UPI ID, Indian phone, PIN)**, and OpenTelemetry dashboards. Great architectural template.
- **NVIDIA NeMo Guardrails / Guardrails AI** — heavier, dialog-flow / validation frameworks; mention as alternatives but they're overkill for 5 days.
- **Browser-extension interception references** — open-source `chainstacklabs/chainstack-dlp-browser-extension` (redacts locally before ChatGPT) and `umair9747/leakyGPT` (secret scanning before submit). The interception mechanic: a content script reads the composer element (ChatGPT `#prompt-textarea` / contenteditable; Gemini uses a Quill `.ql-editor`; Claude its own composer) or hooks `window.fetch`/`XMLHttpRequest` before the send fires; detection can run in the 200–800ms window before submission. **Ethics note for judges:** the same fetch-hooking technique was abused by malware — Urban VPN Proxy, a Chrome extension with 6M+ users (4.7★, "Featured" badge) plus 1.3M Edge installs, silently added AI-chat harvesting in v5.5.0 on July 9, 2025, capturing prompts/responses from 8 platforms (ChatGPT, Claude, Gemini, Copilot, Perplexity, DeepSeek, Grok, Meta AI), affecting ~8M users across 8 related extensions per Koi Security's Dec 2025 report ("Anyone who used ChatGPT, Claude, Gemini... after July 9, 2025 should assume those conversations are now on Urban VPN's servers"). Position your extension as the *defensive*, local-first, privacy-preserving counterpart.

### How to use AMD Developer Cloud + Fireworks sensibly (the architecture justification)
- **AMD Developer Cloud** provides **AMD Instinct MI300X** GPU droplets with **192 GB HBM3** each, running **ROCm**; the **vLLM ROCm** Docker image (`rocm/vllm`) gives an **OpenAI-compatible endpoint in under ~30 minutes**. A single MI300X can hold Llama-3.1-70B unsharded, or run many small models at once (up to 8 single-GPU vLLM instances per 8-GPU node). Per Phoronix's hands-on review, AMD Developer Cloud (which redirects to DigitalOcean GPU Droplets) lists "$1.99 USD per hour for the single MI300X instance or $15.92 per hour for the 8 x MI300X." Hugging Face Transformers and PyTorch also run on ROCm.
- **Fireworks AI** — OpenAI-compatible serverless API for 400+ open models (Llama, Qwen, DeepSeek, Mixtral, Kimi, GLM, **gpt-oss**, and **Gemma**), with **JSON mode, JSON-schema structured output, grammar mode, and function/tool calling** across models; sub-4B models ~$0.10/1M tokens, 4B–16B ~$0.20/1M, >16B dense ~$0.90/1M; LoRA/SFT fine-tuning billed per training token with fine-tuned models served at base price. Fireworks is itself an AMD partner (FireAttention V3 on MI300X).
- **The clean division of labor:**
  - **On the MI300X (AMD Developer Cloud):** host your **first-pass detector** — GLiNER-PII or Piiranha (and optionally a Gemma model via vLLM to chase the $2,000 AMD-Hosted-Gemma bonus) — behind a vLLM/FastAPI endpoint. Justification: 192 GB HBM lets you keep the detector hot with room to spare; it's local, low-latency, and "meaningfully incorporates AMD infrastructure" (a scored criterion). This is your privacy-preserving lane (sensitive text never leaves AMD infra for detection).
  - **On Fireworks:** the **second-stage contextual adjudicator + redaction reasoner + policy explainer**, called with **JSON mode** to return `{entities, risk_level, action, redacted_prompt, rationale}`. Justification: strongest reasoning without you hosting a 70B model; uses the mandated Fireworks credits; keeps token spend contained by only calling on flagged prompts.
- This dual use directly satisfies both required sponsor technologies and gives judges a crisp story: *"AMD GPU for fast, private detection; Fireworks for smart contextual policy."*

## Details

### Recommended end-to-end architecture
```
                    ┌─────────────────────────────────────────────┐
   User types in    │  INTERCEPTION LAYER                          │
   ChatGPT/Claude → │  (a) Browser extension (content script)      │
   OR app calls  →  │  (b) OpenAI-compatible proxy (LiteLLM-style) │
                    └───────────────┬─────────────────────────────┘
                                    │ raw prompt
                                    ▼
                    ┌─────────────────────────────────────────────┐
                    │  DETECTION ENGINE                            │
                    │  Stage 1: Regex + checksums (emails, cards,  │
                    │           SSNs, API keys, JWTs) — instant    │
                    │  Stage 2: GLiNER-PII / Piiranha on MI300X    │
                    │           (vLLM/FastAPI, ROCm) — span+type   │
                    │  Stage 3: Fireworks LLM (JSON mode) —        │
                    │           context adjudication, only if      │
                    │           Stage 1/2 flag medium/ambiguous    │
                    └───────────────┬─────────────────────────────┘
                                    │ entities + confidence + risk
                                    ▼
                    ┌─────────────────────────────────────────────┐
                    │  POLICY ENGINE                               │
                    │  per-entity rules → BLOCK / REDACT / WARN /  │
                    │  ALLOW; reversible Vault (placeholder↔value) │
                    └───────────────┬─────────────────────────────┘
                     safe prompt →  │  → forward to LLM provider
                                    ▼
                    ┌─────────────────────────────────────────────┐
                    │  AUDIT LOG + DASHBOARD                        │
                    │  who/what/when, entity counts, actions,      │
                    │  latency, redaction previews (React/Next)    │
                    └─────────────────────────────────────────────┘
```
Adopt the **reversible "anonymize → LLM → de-anonymize" sandwich** (placeholder tokens in a Vault) so redaction doesn't destroy the model's usefulness — this is what LLM Guard's Anonymize/Deanonymize and PII Shield do, and it's a strong demo moment (the user still gets a useful answer).

### Datasets & evaluation
- **ai4privacy/pii-masking-200k** (and the newer **pii-masking-300k** = OpenPII-220k + FinPII-80k) — the standard synthetic, multilingual (EN/FR/DE/IT) token-classification PII corpus; load via `datasets.load_dataset("ai4privacy/pii-masking-200k")`. Use it to (a) sanity-check your detector, (b) optionally LoRA-fine-tune on Fireworks, (c) generate demo prompts.
- **Nightfall's own sample datasets** (help.nightfall.ai sample_data) — realistic positive + negative-lookalike samples for PII/PCI/PHI/secrets/images; excellent for building your **demo script** and false-positive tests.
- **bigcode/bigcode-pii-dataset**, **StarPII**, and **PIIBench** (2026 unified multi-source benchmark) for stress-testing generalization.
- **Simple metrics to report:** per-entity **precision/recall/F1** (relaxed span match), plus end-to-end **P50/P99 latency** and % of prompts that required the Fireworks stage. Keep claims honest — cite that synthetic F1 overstates real-world performance.

### Team split for 5 people
- **Person A — Detection/ML lead (AMD GPU):** stand up MI300X droplet, vLLM ROCm image, serve GLiNER-PII/Piiranha (and Gemma for the bonus) behind FastAPI; build the regex/checksum layer; run the ai4privacy eval.
- **Person B — Fireworks & policy engine:** Fireworks client with JSON-mode structured output for contextual adjudication + redaction rationale; the policy engine (per-entity BLOCK/REDACT/WARN) and the reversible Vault.
- **Person C — Interception (browser extension):** Chrome MV3 extension with content scripts for chatgpt.com/claude.ai/gemini; intercept composer before send; call backend; render inline warning/redaction UI.
- **Person D — Proxy/gateway + backend glue:** OpenAI-compatible reverse proxy (fork LiteLLM's Presidio pattern or a thin FastAPI shim) for the "apps" use case; API contracts; containerize everything (Docker Compose) — remember **all submissions must be containerized**.
- **Person E — Dashboard, demo, and pitch:** React/Next audit-log dashboard (entity counts, actions, latency, redaction previews); write the README, record the **video + slide deck**, and craft the startup pitch narrative.

### 5-day build plan (July 6–11)
- **Day 1 (Jul 6):** Register/claim credits (do this first — AMD Cloud + Fireworks). Spin up MI300X + vLLM endpoint; validate a "hello LLM" call on both AMD and Fireworks. Lock scope, entity taxonomy, and API contracts. Stub the repo + Docker Compose.
- **Day 2 (Jul 7):** Ship Stage-1 regex + Stage-2 GLiNER/Piiranha on MI300X; Fireworks JSON-mode adjudicator returning typed entities + risk. Basic policy engine (block/redact/warn) + Vault.
- **Day 3 (Jul 8):** Interception layer — browser extension intercepting ChatGPT/Claude AND the proxy path. End-to-end: prompt → detect → redact → forward → de-anonymize response. First integration.
- **Day 4 (Jul 9):** Dashboard + audit log; run ai4privacy/Nightfall-sample eval, record precision/recall + latency; tune thresholds to cut false positives; add the reversible-redaction demo. Polish UX/coaching messages.
- **Day 5 (Jul 10):** Freeze features; containerize + verify clean-run from README; record demo video + slides; write long description emphasizing product/market + AMD usage. Buffer for the **Jul 11, 15:00 UTC** deadline.

### MVP vs stretch goals
- **MVP (must-have for a credible Unicorn submission):** proxy path + browser extension (at least ChatGPT), regex + one MI300X-hosted NER model, Fireworks adjudication, block/redact/warn policy, reversible redaction, audit dashboard, containerized repo, video/slides.
- **Stretch:** prompt-injection/jailbreak scanner (LLM Guard has one), secrets detector expansion, PHI mapping, multi-provider proxy, per-user/group policies, LoRA fine-tune of the detector on Fireworks, **Gemma-on-MI300X** for the $2,000 bonus, India-specific recognizers (Aadhaar/PAN/UPI) à la PII Shield, output-side leakage scanning, SIEM/Slack alert integration.

### Demo strategy (tuned to the rubric)
- **Creativity/Originality:** show the *dual-surface* firewall (human via extension + machine via proxy) and the reversible redaction that preserves answer quality — most guardrail demos only block.
- **Product/Market Potential:** frame as "Nightfall for everyone / open-source shadow-AI DLP." Cite the real risk (the Urban VPN prompt-harvesting incident affecting ~8M users; GDPR Article 25) and the compliance buyer (HIPAA/PCI/GDPR). "Think startup pitch, not benchmark run."
- **Completeness:** live end-to-end demo with a scripted prompt containing a name + SSN + credit card + API key → watch it get redacted, forwarded, and the response de-anonymized; show the audit dashboard updating.
- **Use of AMD Platforms:** explicitly show the detector running on MI300X/ROCm/vLLM (a terminal or dashboard panel with GPU utilization), and pursue the AMD-Hosted Gemma bonus. This is a *scored* criterion — make it visually obvious.

## Recommendations
1. **Commit to Track 3 (Unicorn) and build the dual-surface firewall.** It's the only track that rewards a product/startup narrative, and your idea is a natural fit. Register and claim AMD + Fireworks credits on Day 1 (new-member credits take up to 3 business days, so apply *now*).
2. **Use the cascade detector, not a single model.** Regex → MI300X-hosted GLiNER-PII (best for diverse/Indian names) or Piiranha (best fixed-schema multilingual) → Fireworks JSON-mode adjudicator. Only escalate to Fireworks on flagged/ambiguous prompts to save latency and credits.
3. **Reuse, don't rebuild.** Fork LiteLLM's Presidio-guardrail proxy pattern and study LLM Guard's Anonymize/Vault/Deanonymize for reversible redaction. Use the Microsoft PII Shield FastAPI design as your service template. This is how you finish in 5 days.
4. **Make AMD usage undeniable and chase the Gemma bonus.** Host the detector (and a Gemma model) on MI300X via vLLM; put GPU metrics on the dashboard. That targets both "Use of AMD Platforms" and the extra **$2,000 AMD-Hosted Gemma** prize.
5. **Be honest about accuracy.** Demo on clean in-domain prompts, report precision/recall on ai4privacy, and explicitly acknowledge cross-domain degradation. Judges reward completeness and vision, not benchmark bravado — and over-claiming is a credibility risk.
6. **Nail the deliverables:** containerize everything, write a runnable README, and invest real time in the video + slide pitch — these are hard requirements and the pitch is what the Unicorn judges score.

**Benchmarks that would change the plan:** if by end of Day 2 the MI300X detector isn't stable, fall back to Presidio + GLiNER on CPU in a container and keep the *architecture* story (you can still call it "designed for MI300X"). If Fireworks credits run low, cache adjudications and raise the escalation threshold so only high-risk prompts hit the LLM. If the browser extension proves brittle (composer DOM changes), pivot the live demo to the proxy path (a chat UI pointed at your gateway), which is more robust.

## Caveats
- **Judging weights are not published.** The four Unicorn criteria are named but unweighted; treat all four as roughly equal and don't neglect the pitch.
- **Accuracy claims are fragile.** Headline F1 numbers (Piiranha 98%+, DeBERTa 0.9757, GLiNER ~81%) come mostly from synthetic ai4privacy-style data; independent multi-domain benchmarks show off-the-shelf PII detectors collapsing (PIIBench best F1 ~0.14). Your real-world numbers will be lower.
- **Licensing.** Piiranha's model card lists **CC-BY-NC-ND-4.0** (non-commercial, no-derivatives) — usable for a hackathon demo but not for a commercial product without checking; GLiNER-PII (knowledgator) and LLM Guard (MIT) are safer for a startup pitch. Hackathon submissions must be MIT-compliant, so keep your *own* code MIT and be explicit about third-party model licenses.
- **Model/version drift on Fireworks.** Fireworks' catalog and model names change frequently (400+ models, new weights within ~24h of release); pick whatever current Llama/Qwen/GLM/Gemma instruct model supports JSON mode at demo time rather than hard-coding a name.
- **Browser interception is inherently brittle and ToS-sensitive.** Chatbot DOM structures change; fetch-hooking is the same technique abused by malware. Keep detection local/private, be transparent, and have the proxy path as a fallback demo.
- **Credit limits.** $50 Fireworks + ~$100/50-hrs AMD is enough for a hackathon but not for careless 70B calls or idle GPU droplets — shut the droplet down when not in use (billing is ~$1.99/hr for a single MI300X) and gate Fireworks calls behind the cascade.
- **Reversible redaction has residual risk.** The Vault holds real values server-side; note this in your design as a known limitation (encrypt at rest, short TTL) rather than claiming perfect privacy.
- **LiteLLM Presidio edge cases exist** (e.g., a known open bug with end-to-end un-masking on Anthropic's native API path when tools are present) — test your exact path early.