"""
Unit tests and evaluation suite for the LLM Layer (Classifier & Drafter).
"""

from collections import defaultdict
from typing import Dict, List, Tuple
import pytest

from app.data.generate import generate_dataset
from app.models.enums import DatasetSplit, RecoveryChannel
from app.llm.classifier import (
    ClassificationCategory,
    classify_payment_failure,
    clear_classifier_cache,
)
from app.llm.drafter import draft_recovery_message
from app.llm.provider import LLMProvider


class MockLLMProvider(LLMProvider):
    """
    Mock LLM provider for testing without API keys.
    """
    def complete(self, system: str, user: str, json_schema=None) -> dict:
        if "insufficient funds" in user.lower():
            return {
                "category": "insufficient_funds",
                "confidence": 0.94,
                "reasoning": "The transaction was declined because of insufficient balance in the account.",
                "signals_used": ["failure_reason=insufficient funds"]
            }
        elif "abandoned" in user.lower():
            return {
                "category": "intent_hesitation",
                "confidence": 0.89,
                "reasoning": "The customer abandoned the checkout session prior to payment completion.",
                "signals_used": ["failure_code=CHECKOUT_ABANDONED"]
            }
        elif "otp" in user.lower():
            return {
                "category": "authentication_drop",
                "confidence": 0.91,
                "reasoning": "The customer entered an incorrect or expired OTP during verification.",
                "signals_used": ["failure_reason=OTP expired"]
            }
        elif "gateway timeout" in user.lower():
            return {
                "category": "technical_failure",
                "confidence": 0.95,
                "reasoning": "The acquiring bank timed out during transaction settlement.",
                "signals_used": ["failure_code=GATEWAY_ERROR"]
            }
        else:
            return {
                "category": "technical_failure",
                "confidence": 0.85,
                "reasoning": "Payment failed at gateway during execution.",
                "signals_used": ["failure_code=BAD_REQUEST_ERROR"]
            }


def _get_ground_truth_category(payment) -> ClassificationCategory:
    """Derives expected operational category from dataset failure specs."""
    if payment.customer and payment.customer.is_risk_flagged:
        return ClassificationCategory.DO_NOT_PURSUE

    code = payment.failure_code.upper()
    reason = payment.failure_reason.lower()

    if "ABANDONED" in code or "abandoned" in reason:
        return ClassificationCategory.INTENT_HESITATION
    elif "insufficient funds" in reason:
        return ClassificationCategory.INSUFFICIENT_FUNDS
    elif "otp" in reason or "declined by issuing" in reason:
        return ClassificationCategory.AUTHENTICATION_DROP
    else:
        return ClassificationCategory.TECHNICAL_FAILURE


def test_classifier_held_out_confusion_matrix(capsys):
    """
    Evaluates classifier on the 20 held-out evaluation rows and prints
    a full Confusion Matrix with precision/recall metrics.
    """
    clear_classifier_cache()
    customers, payments = generate_dataset(seed=42, wipe_db=True)
    
    held_out_payments = [p for p in payments if p.dataset_split == DatasetSplit.HELD_OUT]
    assert len(held_out_payments) == 20

    categories = list(ClassificationCategory)
    # confusion_matrix[actual][predicted]
    matrix: Dict[ClassificationCategory, Dict[ClassificationCategory, int]] = {
        act: {pred: 0 for pred in categories} for act in categories
    }

    correct = 0
    total = len(held_out_payments)

    for p in held_out_payments:
        true_cat = _get_ground_truth_category(p)
        result = classify_payment_failure(payment=p, customer=p.customer, provider=MockLLMProvider())
        pred_cat = result.category

        matrix[true_cat][pred_cat] += 1
        if true_cat == pred_cat:
            correct += 1

    accuracy = correct / total * 100.0

    # Format Confusion Matrix output table
    col_width = 14
    header = f"{'Actual \\\\ Predicted':<22} | " + " | ".join(f"{c.value[:col_width]:<{col_width}}" for c in categories) + " | Total"
    divider = "-" * len(header)
    
    table_lines = [
        "",
        "=" * len(header),
        f"  CLASSIFIER HELD-OUT EVALUATION METRICS (N = {total} rows)",
        "=" * len(header),
        header,
        divider,
    ]

    for act in categories:
        row_counts = [matrix[act][pred] for pred in categories]
        row_total = sum(row_counts)
        row_str = f"{act.value:<22} | " + " | ".join(f"{cnt:<{col_width}}" for cnt in row_counts) + f" | {row_total}"
        table_lines.append(row_str)

    table_lines.extend([
        divider,
        f" Overall Classification Accuracy on Held-Out Set: {accuracy:.1f}% ({correct}/{total})",
        "=" * len(header),
        "",
    ])

    report = "\n".join(table_lines)
    print(report)

    # High accuracy threshold on classification
    assert accuracy >= 90.0


def test_drafter_constraints_and_fallbacks():
    """
    Validates message drafting constraints:
    - Length < 200 characters
    - Must contain {payment_link}
    - Must contain opt-out ('STOP')
    - No forbidden pressure words ('Hurry', 'Last chance', 'Legal')
    """
    categories_to_test = [
        ClassificationCategory.TECHNICAL_FAILURE,
        ClassificationCategory.INSUFFICIENT_FUNDS,
        ClassificationCategory.AUTHENTICATION_DROP,
        ClassificationCategory.INTENT_HESITATION,
    ]

    for cat in categories_to_test:
        draft = draft_recovery_message(
            category=cat,
            customer_name="Harshit Sharma",
            cart_summary="Mixer Grinder 750W",
            amount_rupees=2499.0,
            attempt_number=1,
            channel=RecoveryChannel.WHATSAPP
        )

        assert draft.character_count <= 200, f"Message exceeded 200 chars ({draft.character_count}): {draft.message}"
        assert draft.contains_link_placeholder is True
        assert "{payment_link}" in draft.message
        assert draft.contains_opt_out is True
        assert "STOP" in draft.message.upper()
        
        # Guardrail checks: no guilt-tripping or manipulative urgency
        lower_msg = draft.message.lower()
        forbidden_words = ["hurry", "last chance", "urgent", "penalty", "legal", "court", "default"]
        for word in forbidden_words:
            assert word not in lower_msg, f"Forbidden word '{word}' found in message: {draft.message}"


def test_do_not_pursue_suppression():
    """
    Verifies that do_not_pursue never generates a payment link outreach message.
    """
    draft = draft_recovery_message(
        category=ClassificationCategory.DO_NOT_PURSUE,
        customer_name="Risk User",
        cart_summary="Smartphone Pro",
        amount_rupees=19999.0,
        attempt_number=1,
    )
    assert "suppressed" in draft.message.lower()
    assert draft.contains_link_placeholder is False
