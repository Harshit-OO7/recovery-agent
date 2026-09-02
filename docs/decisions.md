# Design Decisions & Architecture Trade-Offs

This document details the critical architectural decisions made during the design of the Razorpay AI Revenue Recovery Agent, including alternatives evaluated and rejected.

---

## Decision 1: Post-Checkout Recovery vs In-Session Optimization

* **Decision**: Focus exclusively on asynchronous post-checkout revenue recovery, operating hours or days after a checkout transaction has failed.
* **Alternative Evaluated**: Real-time in-session payment routing and dynamic retries (competing with Razorpay Optimizer).
* **Rationale for Rejection**:
  - Razorpay Optimizer is already best-in-class for sub-second in-session routing, downtime detection, and terminal redundancy during checkout.
  - When all in-session retries fail (e.g. UPI app timeout, card limits exceeded, authentication challenge abandoned), the transaction terminates and the buyer leaves the site.
  - No existing automated system analyzes the psychological and technical context of that drop-off to orchestrate respectful, multi-channel recovery after the session is closed.
  - Post-checkout recovery requires understanding buyer intent, liquidity timing (e.g. salary cycles), and contact fatigue?problems uniquely suited for autonomous agentic reasoning.

---

## Decision 2: Strictly Deterministic Policy Engine vs End-to-End LLM Control

* **Decision**: Enforce a rigid boundary where the LLM is restricted to classification and copywriting, while all operational decisions (dispatch, wait, suppress, escalate) are governed by 7 hard-coded deterministic gates.
* **Alternative Evaluated**: Allowing the LLM to directly decide actions (e.g. prompt: *"Decide whether to send a payment link to this customer"*).
* **Rationale for Rejection**:
  - **Fiduciary Risk**: An LLM can hallucinate, drift under adversarial prompts, or disregard budget thresholds.
  - **Auditability**: Compliance officers and financial auditors require deterministic explanations for why a customer was contacted or suppressed (e.g. *"Suppressed by Gate G2: Cart value Rs. 75 < Rs. 100 threshold"*).
  - **Safety Invariants**: Deterministic gates allow formal property-based verification (e.g., proving with 100% certainty that risk-flagged customers never receive outreach).
  - **What-If Simulations**: Separating policy rules allows operators to tune thresholds in real time without paying for LLM inference.

---

## Decision 3: Seed-Isolated Customer Simulator vs Live Outreach

* **Decision**: Build a deterministic, seed-isolated customer behavior simulator with explicit propensity archetypes and multiplicative decay curves.
* **Alternative Evaluated**: Dispatching live test messages to arbitrary phone numbers or mocking instant 100% success.
* **Rationale for Rejection**:
  - Real abandoned checkout customers cannot be contacted without active merchant agreements and live customer consent.
  - A naive mock that assumes 100% recovery is dishonest and useless for benchmark evaluation.
  - The simulator provides a realistic, reproducible counterfactual ground truth. The agent never sees the customer's private propensity profile (`reliable`, `distracted`, `hesitant`, `broke`, `ghost`), preventing artificial benchmark leakage.

---

## Decision 4: Non-Bypassable Contact Frequency Limits

* **Decision**: Hard-code a maximum of 2 recovery attempts per transaction in the core policy engine ($G3$), making it impossible to disable or bypass from the UI.
* **Alternative Evaluated**: Providing an unrestricted toggle allowing merchants to set infinite retry attempts.
* **Rationale for Rejection**:
  - Repeatedly contacting buyers who have ignored outreach constitutes spam and harassment, inflicting long-term brand damage on merchants and degrading customer trust in Razorpay payment links.
  - Enforcing a mathematical cap of 2 attempts balances recovery potential against customer annoyance.

---

## Decision 5: Real Razorpay Test API Integration vs Synthetic Mock Links

* **Decision**: Wire all successful recovery decisions to the real Razorpay Test Mode API to generate genuine, clickable `https://rzp.io/i/...` short links with real order references and idempotency guards.
* **Alternative Evaluated**: Returning fake mock URLs like `http://example.com/pay`.
* **Rationale for Rejection**:
  - Using the real Razorpay Python SDK proves end-to-end viability: proper authentication, payload validation, idempotency keying, and graceful handling of upstream gateway errors.
