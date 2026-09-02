# Razorpay AI Revenue Recovery Agent ? Benchmark & Evaluation Results

> **Track 3 (AI Revenue Recovery) Evaluation Report**  
> *Generated on: 2026-09-02 17:08:58 UTC | Master Seed: `42`*

---

## 1. Executive Summary & Recovery Lift

| Metric | Agentic Recovery | Zero-Intervention Baseline | Net Lift / Uplift |
| :--- | :--- | :--- | :--- |
| **Recovered Transactions** | **31** (38.8%) | 9 (11.2%) | **+27.6%** (3.46x Lift) |
| **Recovered Revenue** | **Rs. 137,669.00** | Rs. 86,791.00 | **+Rs. 50,878.00** |
| **Value at Risk (Cohort)** | Rs. 485,800.00 | Rs. 485,800.00 | 80 Failed Transactions |
| **Median Time to Recovery** | **28.0 hours** | 48.0 hours | ~2x Faster Resolution |

---

## 2. Unit Economics & ROI

- **Assumed Cost per Contact**: Rs. 0.50 (WhatsApp/SMS Business API)
- **Total Outreach Messages Sent**: 84 contacts
- **Total Outreach Spend**: Rs. 42.00
- **Cost per Recovered Payment**: **Rs. 1.35**
- **Net ROI Ratio**: **1,211x** (Rs. 50,878.00 recovered per Rs. 42.00 spent)

---

## 3. Restraint & Policy Suppression Audit

Our deterministic policy engine suppresses wasteful or risky outreach before any messages are sent:

| Hard Gate | Trigger Condition | Transactions Suppressed | Protected / Saved Value |
| :--- | :--- | :--- | :--- |
| **G1** | do_not_contact (Risk / Opt-out) | 14 (17.5%) | Rs. 97,966.00 |
| **G2** | value_floor (< Rs 100 cost ceiling) | 9 (11.2%) | Rs. 491.00 |
| **G3** | max_attempts (Fatigue cap) | 1 (1.2%) | Rs. 26,999.00 |
| **Total** | **All Suppression Gates** | **24** (30.0%) | **Rs. 125,456.00** |

---

## 4. Root Cause Classifier Performance (Held-Out Test Set, N = 20)

**Overall Classification Accuracy**: `100.0%` (20/20 correct)

| Intent Category | Precision | Recall | F1-Score | Support |
| :--- | :--- | :--- | :--- | :--- |
| `technical_failure` | 1.00 | 1.00 | 1.00 | 7 |
| `insufficient_funds` | 1.00 | 1.00 | 1.00 | 2 |
| `authentication_drop` | 1.00 | 1.00 | 1.00 | 2 |
| `intent_hesitation` | 1.00 | 1.00 | 1.00 | 4 |
| `do_not_pursue` | 1.00 | 1.00 | 1.00 | 5 |

---

## 5. Honest Methodology & Evaluation Limitations

> [!IMPORTANT]
> **Transparency & Methodology Disclosures:**
> 1. **Synthetic Dataset**: All 80 transaction records and 55 customer profiles are deterministically synthesized based on Razorpay checkout failure distribution benchmarks.
> 2. **Simulated Customer Response**: Customer payment outcomes and opt-outs are governed by an honest, seed-locked mathematical probability model with propensity profiles, attempt decays, and failure cause alignments.
> 3. **Sample Size**: Evaluated on $N = 80$ transactions (60 train / 20 held-out split).
> 4. **Zero Live Merchant Data**: No real proprietary merchant database or customer PII was ingested or processed.
> 5. **Counterfactual Baseline**: Lift is strictly benchmarked against a zero-intervention baseline under the exact same seed.
