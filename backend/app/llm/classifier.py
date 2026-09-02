"""
Failure Reason and Customer Intent Classifier.

Architectural Rule #1:
The LLM classifies and drafts. It never decides whether money moves.
The classifier ingests observable transaction and customer signals (NEVER propensity ground truth)
and maps them to a standardized operational recovery category.
"""

from enum import Enum
import logging
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from app.llm.provider import LLMProvider, get_llm_provider, LLMProviderError
from app.models.failed_payment import FailedPayment
from app.models.customer import Customer
from app.schemas.customer import CustomerAgentView

logger = logging.getLogger("app.llm.classifier")


class ClassificationCategory(str, Enum):
    TECHNICAL_FAILURE = "technical_failure"       # Gateway or network problem, customer intended to pay
    INSUFFICIENT_FUNDS = "insufficient_funds"     # Customer wanted to pay but account had insufficient balance
    AUTHENTICATION_DROP = "authentication_drop"   # OTP, 3DS, or card CVV/expiry failure, likely recoverable
    INTENT_HESITATION = "intent_hesitation"       # Abandoned at checkout session, considering, needs nudge
    DO_NOT_PURSUE = "do_not_pursue"               # Risk-flagged, fraudulent chargeback history, do not contact


class ClassificationResult(BaseModel):
    """
    Structured outcome of the classification stage.
    """
    category: ClassificationCategory
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    reasoning: str = Field(..., description="Plain-English explanation without jargon for UI display")
    signals_used: List[str] = Field(default_factory=list, description="List of specific input signals leveraged")
    llm_fallback: bool = Field(False, description="True if deterministic fallback was engaged due to LLM failure")


# In-memory cache keyed by payment_id to prevent redundant token consumption
_CLASSIFICATION_CACHE: Dict[str, ClassificationResult] = {}


def clear_classifier_cache() -> None:
    """Clears the in-memory classification cache."""
    global _CLASSIFICATION_CACHE
    _CLASSIFICATION_CACHE.clear()


SYSTEM_PROMPT = """You are an expert payment recovery intelligence agent for an Indian e-commerce merchant using Razorpay.
Your job is to analyze failed checkout transactions and classify the root cause into exactly ONE of the following 5 categories:

1. technical_failure: Gateway timeout, network glitch, or acquiring bank downtime where customer intent was clear.
2. insufficient_funds: Bank reported insufficient account balance or credit limit exceeded.
3. authentication_drop: OTP expired/incorrect, 3DS challenge timeout, or card details verification issue.
4. intent_hesitation: Customer abandoned checkout before completing payment, considering price or product.
5. do_not_pursue: Customer is marked as high-risk, dispute-prone, or repeatedly fraudulent.

CRITICAL RULES:
- If 'is_risk_flagged' is true, ALWAYS classify as 'do_not_pursue'.
- Output clear, empathetic plain-English reasoning in 1-2 sentences suitable for a merchant dashboard.
- Return strictly valid JSON conforming to the requested schema.
"""


def _build_user_prompt(payment: FailedPayment, customer_data: Dict[str, Any]) -> str:
    amount_rupees = payment.amount_paise / 100.0
    return f"""Analyze this failed payment:
- Transaction ID: {payment.id}
- Amount: Rs. {amount_rupees:.2f}
- Payment Method: {payment.method.value if hasattr(payment.method, 'value') else payment.method}
- Razorpay Failure Code: {payment.failure_code}
- Razorpay Failure Reason: {payment.failure_reason}
- Cart Summary: {payment.cart_summary}
- Customer City: {customer_data.get('city', 'Unknown')}
- Total Past Successful Payments: {customer_data.get('history_total_payments', 0)}
- Total Past Failed Payments: {customer_data.get('history_failed_payments', 0)}
- Average Days to Pay: {customer_data.get('history_avg_days_to_pay', 0.0)}
- Is Risk Flagged: {customer_data.get('is_risk_flagged', False)}

Return JSON with keys:
"category" (one of: technical_failure, insufficient_funds, authentication_drop, intent_hesitation, do_not_pursue)
"confidence" (float 0.0 to 1.0)
"reasoning" (1-2 clear plain English sentences)
"signals_used" (list of key strings)
"""


def deterministic_fallback_classifier(
    payment: FailedPayment,
    customer_data: Dict[str, Any]
) -> ClassificationResult:
    """
    Deterministic rule-based backup classifier.
    Guarantees that recovery runs never fail or stall even if LLM APIs are offline.
    """
    is_risk = customer_data.get("is_risk_flagged", False)
    if is_risk:
        return ClassificationResult(
            category=ClassificationCategory.DO_NOT_PURSUE,
            confidence=0.98,
            reasoning="Customer account is flagged for payment risk or prior disputes. Contact is suppressed.",
            signals_used=["is_risk_flagged=True"],
            llm_fallback=True,
        )

    code_upper = str(payment.failure_code).upper()
    reason_lower = str(payment.failure_reason).lower()

    if "ABANDONED" in code_upper or "abandoned" in reason_lower:
        return ClassificationResult(
            category=ClassificationCategory.INTENT_HESITATION,
            confidence=0.88,
            reasoning="Customer closed or left checkout before payment execution, indicating hesitation or distraction.",
            signals_used=["failure_code=CHECKOUT_ABANDONED", "cart_summary=" + payment.cart_summary],
            llm_fallback=True,
        )

    if "GATEWAY_ERROR" in code_upper or "timeout" in reason_lower or "gateway" in reason_lower and "failed at payment gateway" not in reason_lower:
        return ClassificationResult(
            category=ClassificationCategory.TECHNICAL_FAILURE,
            confidence=0.92,
            reasoning="The acquiring bank or gateway timed out during processing while the customer attempted to pay.",
            signals_used=["failure_code=GATEWAY_ERROR", "failure_reason=" + payment.failure_reason],
            llm_fallback=True,
        )

    if "insufficient funds" in reason_lower or "funds" in reason_lower:
        return ClassificationResult(
            category=ClassificationCategory.INSUFFICIENT_FUNDS,
            confidence=0.95,
            reasoning="The transaction was declined due to insufficient available balance in the customer's account.",
            signals_used=["failure_reason=insufficient funds", f"amount=Rs.{payment.amount_paise/100.0:.2f}"],
            llm_fallback=True,
        )

    if "otp" in reason_lower or "expired" in reason_lower or "declined by issuing bank" in reason_lower:
        return ClassificationResult(
            category=ClassificationCategory.AUTHENTICATION_DROP,
            confidence=0.89,
            reasoning="Customer experienced an authentication or card verification drop during OTP/bank validation.",
            signals_used=["failure_reason=" + payment.failure_reason, f"method={payment.method}"],
            llm_fallback=True,
        )

    # General gateway error / payment_failed
    return ClassificationResult(
        category=ClassificationCategory.TECHNICAL_FAILURE,
        confidence=0.80,
        reasoning="Payment failed at the gateway during transaction settlement.",
        signals_used=["failure_code=" + payment.failure_code, "failure_reason=" + payment.failure_reason],
        llm_fallback=True,
    )


def classify_payment_failure(
    payment: FailedPayment,
    customer: Union[Customer, CustomerAgentView, Dict[str, Any]],
    provider: Optional[LLMProvider] = None,
    use_cache: bool = True,
    force_llm_failure: bool = False,
) -> ClassificationResult:
    """
    Classifies a payment failure using the configured LLM provider with caching,
    strict schema validation, and automatic rule-based fallback.
    """
    if not force_llm_failure and use_cache and payment.id in _CLASSIFICATION_CACHE:
        return _CLASSIFICATION_CACHE[payment.id]

    # Extract non-sensitive customer context (NEVER propensity ground truth)
    if isinstance(customer, dict):
        cust_data = customer
    elif hasattr(customer, "__dict__"):
        cust_data = {
            "city": getattr(customer, "city", "Unknown"),
            "history_total_payments": getattr(customer, "history_total_payments", 0),
            "history_failed_payments": getattr(customer, "history_failed_payments", 0),
            "history_avg_days_to_pay": getattr(customer, "history_avg_days_to_pay", 0.0),
            "is_risk_flagged": getattr(customer, "is_risk_flagged", False),
        }
    else:
        cust_data = {}

    # Controlled Failure Injection for Live Demonstration
    if force_llm_failure:
        logger.warning(f"[FAILURE INJECTION ACTIVE] Simulating malformed LLM response for payment {payment.id}. Engaging deterministic fallback classifier.")
        result = deterministic_fallback_classifier(payment, cust_data)
        result.reasoning = f"[FALLBACK ENGAGED - LLM ERROR HANDLED] {result.reasoning}"
        if use_cache:
            _CLASSIFICATION_CACHE[payment.id] = result
        return result

    # Fast-path for risk-flagged accounts
    if cust_data.get("is_risk_flagged", False):
        result = deterministic_fallback_classifier(payment, cust_data)
        if use_cache:
            _CLASSIFICATION_CACHE[payment.id] = result
        return result

    from app.config import settings
    if not settings.LLM_API_KEY or settings.LLM_API_KEY.startswith("your_") or settings.LLM_API_KEY.strip() == "":
        result = deterministic_fallback_classifier(payment, cust_data)
        if use_cache:
            _CLASSIFICATION_CACHE[payment.id] = result
        return result

    if provider is None:
        provider = get_llm_provider()

    user_prompt = _build_user_prompt(payment, cust_data)

    # Attempt LLM completion with 1 retry on malformed JSON
    for retry in range(2):
        try:
            raw_response = provider.complete(
                system=SYSTEM_PROMPT,
                user=user_prompt,
            )

            # Validate against Pydantic schema
            category_raw = str(raw_response.get("category", "")).lower()
            category_enum = ClassificationCategory(category_raw)

            result = ClassificationResult(
                category=category_enum,
                confidence=float(raw_response.get("confidence", 0.85)),
                reasoning=str(raw_response.get("reasoning", "Classified based on observed gateway signals.")),
                signals_used=list(raw_response.get("signals_used", ["failure_code", "failure_reason"])),
                llm_fallback=False,
            )
            if use_cache:
                _CLASSIFICATION_CACHE[payment.id] = result
            return result

        except (LLMProviderError, ValueError, KeyError) as e:
            logger.warning(f"LLM classification attempt {retry + 1} failed with error: {e}")
            if retry == 1:
                logger.info(f"Engaging deterministic rule-based fallback for payment {payment.id}")
                result = deterministic_fallback_classifier(payment, cust_data)
                if use_cache:
                    _CLASSIFICATION_CACHE[payment.id] = result
                return result

    # Catch-all fallback
    result = deterministic_fallback_classifier(payment, cust_data)
    if use_cache:
        _CLASSIFICATION_CACHE[payment.id] = result
    return result
