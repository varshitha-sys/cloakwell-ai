# CLOAKWELL DLP — Verification & Testing Prompts

This document contains categorized testing prompts designed to evaluate the CLOAKWELL Data Loss Prevention (DLP) layer. You can copy and paste these into the **Compliance Dashboard sandbox** (`http://localhost:8000/`) or your browser textarea (e.g., ChatGPT/Gemini) if the extension is enabled.

---

## Category 1: Benign Prompts (Expected: `INFO`)
*These prompts contain no PII or sensitive corporate context. They should pass through completely untouched without triggering any modals or redactions.*

* **Prompt 1 (General Q&A):**
  ```text
  Can you explain the difference between a binary search tree and a hash map in terms of time complexity?
  ```
* **Prompt 2 (Refactoring):**
  ```text
  Please help me refactor this Python list comprehension to be more readable for a junior engineer:
  [x**2 for x in range(10) if x % 2 == 0]
  ```
* **Prompt 3 (Creative Writing):**
  ```text
  Draft a polite email to my team letting them know that I will be out of the office next Monday for a routine doctor's appointment.
  ```

---

## Category 2: Structured PII & Secrets (Expected: `ACTION_NEEDED` / `BLOCK`)
*These prompts contain pattern-based data (emails, SSNs, Aadhaar, API keys) caught by **Tier 1 (regex)**. They should trigger redaction overlays or block modals.*

* **Prompt 1 (Email & Phone - Expected: Redact / `ACTION_NEEDED`):**
  ```text
  Hello, please register my account. My email is sarah.connor@gmail.com and you can reach me at +91 9876543210. Let me know when it's done.
  ```
* **Prompt 2 (Aadhaar & PAN - Expected: Redact / `ACTION_NEEDED`):**
  ```text
  Can you verify if this customer application is valid? The applicant's Aadhaar number is 9999 4105 7058 and their PAN is ABCDE1234F.
  ```
* **Prompt 3 (API Key - Expected: Hard Block / `BLOCK`):**
  ```text
  I am getting an authentication error when trying to call my server. Here is the call:
  curl -H "Authorization: Bearer sk-live-556677889900abcdef123" https://api.initech.internal/v1/deploy
  ```

---

## Category 3: Watchlist Proper Nouns (Expected: `ACTION_NEEDED` / `BLOCK`)
*These prompts contain Initech's specific sensitive terminology defined in `policy.yaml` (Codenames, Hostnames, Acquisitions). They should be parsed, flagged, and redacted.*

* **Prompt 1 (Project Codename - Expected: `ACTION_NEEDED`):**
  ```text
  Can you write a marketing description for our new enterprise software, Project Falcon? Focus on scalability and security.
  ```
* **Prompt 2 (Infrastructure Hostname - Expected: `ACTION_NEEDED` or `BLOCK`):**
  ```text
  Draft a bash script to back up all databases hosted on prod-db-07.initech.internal to the cloud.
  ```
* **Prompt 3 (Acquisition target - Expected: `ACTION_NEEDED`):**
  ```text
  Write a press release announcing Initech's upcoming acquisition of Acme Corp, scheduled for next quarter.
  ```

---

## Category 4: Contextual Policy Violations (Expected: `ACTION_NEEDED` / `BLOCK`)
*These prompts contain no structured PII and no exact watchlist names, but violate the confidentiality policy (e.g., sharing pre-earnings margins, unreleased internal plans). This requires **Tier 2 (Gemma/Llama)** contextual reasoning.*

* **Prompt 1 (Pre-Earnings Financials - Expected: `ACTION_NEEDED`):**
  ```text
  Can you summarize this quarter's performance for my executive slides? Our gross margins dropped by 4.2% and we are currently operating at a net loss of $1.2M, which we cannot make public yet.
  ```
* **Prompt 2 (Internal Infrastructure - Expected: `BLOCK` or `ACTION_NEEDED`):**
  ```text
  Our database is slow. We use PostgreSQL behind an internal reverse proxy with credentials databaseuser:P@ssword123. How do we tune the buffer pool sizes?
  ```
* **Prompt 3 (Unreleased Internal restructure - Expected: `ACTION_NEEDED`):**
  ```text
  We are planning to lay off 15% of our engineering division next month. How should we announce this internal restructure to minimize negative impact on team morale?
  ```
