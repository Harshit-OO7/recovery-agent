# System Architecture & Technical Specification

![System Architecture](architecture.svg)

## 1. Overview & Core Distinction

**Razorpay Optimizer** prevents payment failures *inside* the active checkout session (via dynamic gateway routing, smart retry, card downtime detection, and terminal redundancy).

The **Razorpay AI Revenue Recovery Agent** operates *after* the checkout session has failed. It autonomously ingests post-checkout failure webhooks, diagnoses root causes using LLMs, applies deterministic mathematical safety gates, and executes targeted, respectful recovery workflows using 1-click Razorpay test payment links.

```
Failed Checkout Event (Webhook)
               ?
               ?
   [1. Ingestion & Context] ??(Excludes Simulator Ground Truth)???
               ?                                                 ?
               ?                                                 ?
     [2. LLM Intent Layer]                                       ?
  (Classifier & Drafter + Rule Fallback)                          ?
               ?                                                 ?
               ?                                                 ?
  [3. Deterministic Policy Engine] ???????????????????????????????
      (7 Hard Sequential Gates)
               ?
   ?????????????????????????????????????
   ?           ?           ?           ?
[PASS]    [SUPPRESS]    [WAIT]    [ESCALATE]
   ?           ?           ?           ?
   ?           ?           ?           ?
   ?      (Logged to   (Re-queued   (Assigned
   ?       Exceptions)  to Clock)   to Human)
   ?
[4. Executor & Razorpay API] ??? (1-Click Test Link: https://rzp.io/i/...)
   ?
   ?
[5. Simulator Engine] ??? (Probabilistic Customer Response)
   ?
   ?
[6. SSE Feed & Audit Ledger] ??? (Real-Time React Dashboard & CSV Export)
```

---

## 2. Why Classification and Decision-Making Are Strictly Separated

This architectural boundary is the core defense of the system.

```
??????????????????????????????????????????????????????????
?                   PERCEPTUAL LAYER (LLM)               ?
?  "What happened?" ? Semantic Diagnosis ? Copy Drafting ?
?  Inputs: Error strings, bank failure codes, cart text  ?
?  Output: Probabilistic category & confidence (0.0-1.0) ?
??????????????????????????????????????????????????????????
                            ? (Structured Schema)
                            ?
??????????????????????????????????????????????????????????
?               DETERMINISTIC POLICY ENGINE              ?
?       "Should money move?" ? Operational Restraint     ?
?   Inputs: Hard numerical gates, budget ceilings, caps  ?
?   Output: Pass / Suppress / Wait / Escalate            ?
??????????????????????????????????????????????????????????
```

### The Three Invariants

1. **LLMs are Probabilistic Pattern Engines, Not Fiduciary Controllers**:
   LLMs excel at deciphering noisy, unstructured strings (e.g. converting cryptic error `BAD_REQUEST_GATEWAY_TIMEOUT_NA` into `technical_failure`). However, relying on an LLM to decide whether to dispatch money-touching actions introduces severe risks of prompt injection, non-deterministic boundary drift, and hallucinations.
2. **Provable Safety Guarantees via Property-Based Invariants**:
   By placing a deterministic policy engine between the LLM and the payment link generator, we can write formal property-based tests (e.g., with Hypothesis) asserting that *no risk-flagged customer can ever receive a payment link*, regardless of what category or confidence score the LLM hallucinates.
3. **Instant What-If Simulations Without Token Costs**:
   Because policy thresholds ($G2$ Value Floor, $G3$ Fatigue Cap, $G6$ Confidence Floor) are decoupled from the LLM classifier, operators can drag dashboard sliders to instantly simulate the financial impact of policy changes over past cohorts in $<10	ext{ms}$ without re-calling LLM APIs.

---

## 3. Module-by-Module Walkthrough

### A. Data Layer (`backend/app/data/`, `backend/app/models/`)
- **`models/`**: SQLAlchemy models for `Customer`, `FailedPayment`, `RecoveryAttempt`, and `AuditLog`.
- **Private Simulator Ground Truth**: `Customer.propensity_profile` (`reliable`, `distracted`, `hesitant`, `broke`, `ghost`) is strictly isolated to the simulation engine. The agent's schema imports [`CustomerAgentView`](file:///C:/Users/harsh/.gemini/antigravity/scratch/recovery-agent/backend/app/schemas/customer.py), which explicitly omits this field to prevent data leakage and artificial benchmark cheating.
- **`generate.py`**: Deterministic dataset generator producing 80 realistic Indian checkout failure records calibrated against industry failure distributions (UPI timeouts, 3DS authentication drops, balance declines, checkout abandonments).

### B. LLM Reasoning Layer (`backend/app/llm/`)
- **`provider.py`**: Abstract `LLMProvider` interface with exponential backoff retries, JSON schema enforcement, and timeouts.
- **`classifier.py`**: Diagnoses failure causes into 5 mutually exclusive archetypes: `technical_failure`, `insufficient_funds`, `authentication_drop`, `intent_hesitation`, and `do_not_pursue`. Features an automated rule-based fallback classifier that handles API outages with 0 batch crashes.
- **`drafter.py`**: Generates respectful, empathetic Hinglish/English outreach copy strictly under 200 characters with mandatory opt-out footers (*"Reply STOP to opt out"*).

### C. Deterministic Policy Engine (`backend/app/policy/`)
- **`policy.py`**: Evaluates 7 sequential hard gates with zero external dependencies or LLM calls:
  - **$G1$ `do_not_contact`**: Permanent suppression for risk flags or prior opt-outs.
  - **$G2$ `value_floor`**: Suppresses outreach when cart amount $< 	ext{Rs. } 100.00$ (cost of contact exceeds expected recovery).
  - **$G3$ `max_attempts`**: Hard cap of 2 contact attempts per transaction to prevent customer fatigue.
  - **$G4$ `cooldown`**: Mandatory 24-hour spacing between consecutive contacts.
  - **$G5$ `quiet_hours`**: Blocks outreach outside $09:00 - 20:00	ext{ IST}$ daytime window.
  - **$G6$ `confidence_floor`**: Escalates cases with classification confidence $< 55\%$ to human support.
  - **$G7$ `category_routing`**: Maps intent categories to optimal recovery actions (immediate payment link, reminder without link, or liquidity cooldown).

### D. Executor & Razorpay Integration (`backend/app/executor/`)
- **`razorpay_client.py`**: Wraps the official Razorpay SDK in test mode. Implements idempotency guards keyed on `reference_id` to prevent duplicate link creation.
- **`executor.py`**: Executes the policy decision, requests message drafting, creates Razorpay test links (`https://rzp.io/i/...`), and writes immutable audit logs.

### E. Customer Response Simulator (`backend/app/simulator/`)
- **`engine.py`**: Honest, seed-isolated simulation of customer payment outcomes. Combines base propensity with multiplicative modifiers:
  - Action-to-failure match boost ($+15\%$)
  - Multi-attempt fatigue decay (Attempt 2: $-35\%$, Attempt 3+: $-65\%$)
  - High cart-value deliberation friction ($> 	ext{Rs. } 10,000$: $-15\%$)
  - Antisocial hour annoyance penalty

### F. Orchestrator & Evaluation (`backend/app/orchestrator/`, `backend/app/eval/`)
- **`runner.py`**: Main state machine resolving batch transactions to final states (`recovered`, `suppressed`, `abandoned`, `escalated`).
- **`clock.py`**: Demo clock accelerator supporting $28,800	imes$ speed (24-hour cooldown resolves in 3.0s) while tracking real virtual timestamps.
- **`metrics.py`**: Computes conservative recovery metrics and enforces seed-matching guards during head-to-head baseline comparisons.

### G. Interactive Instrument UI (`frontend/src/`)
- **Vite + React + TypeScript + Tailwind CSS** dashboard featuring live SSE decision feed, slide-over audit drawer with smartphone message preview, what-if parameter sliders, side-by-side comparison modal, and 1-click CSV audit export.
