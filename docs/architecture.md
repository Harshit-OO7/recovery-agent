# Architecture Overview

## Razorpay AI Revenue Recovery Agent (Post-Checkout Recovery)

### Separation of Concerns:
1. **LLM Layer (`app/llm/`)**:
   - Classifies failure reason and customer intent
   - Drafts empathetic, context-aware recovery messages
   - *Never moves money or decides policy rules*

2. **Policy Engine (`app/policy/`)**:
   - Deterministic, hard-coded rules and safety gates
   - Enforces frequency caps, cool-downs, and stopping rules
   - Evaluates when **NOT** to act (Restraint)

3. **Executor (`app/executor/`)**:
   - Interacts with Razorpay APIs in **TEST MODE ONLY**
   - Generates payment recovery links and smart invoices

4. **Auditing and Metrics (`app/models/`, `app/eval/`)**:
   - Every decision is recorded in audit logs with its rationale
   - Reports recovery lift strictly against identical no-intervention baselines
