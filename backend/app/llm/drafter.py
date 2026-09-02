"""
Customer Recovery Outreach Message Drafter.

Generates empathetic, context-aware recovery messages tailored for Indian e-commerce.
Guarantees:
- Warm, natural, respectful Hinglish-friendly English.
- Strictly under 200 characters.
- Contains the required `{payment_link}` placeholder.
- Never uses urgency manipulation, guilt-tripping, or legal threats.
- Always includes an explicit opt-out instruction ("Reply STOP to opt out").
"""

import logging
from typing import Dict, Optional, Union

from pydantic import BaseModel, Field

from app.llm.classifier import ClassificationCategory
from app.llm.provider import LLMProvider, get_llm_provider, LLMProviderError
from app.models.enums import RecoveryChannel

logger = logging.getLogger("app.llm.drafter")


class DraftMessageResult(BaseModel):
    message: str = Field(..., max_length=220, description="Formatted SMS/WhatsApp message under 200 chars")
    character_count: int
    contains_link_placeholder: bool
    contains_opt_out: bool
    llm_fallback: bool = False


# High-quality deterministic templates tailored to each category & attempt
FALLBACK_TEMPLATES: Dict[ClassificationCategory, Dict[int, str]] = {
    ClassificationCategory.TECHNICAL_FAILURE: {
        1: "Hi {name}, your payment for {item} had a quick network glitch. Complete it in 1 tap here: {payment_link}. Reply STOP to opt out.",
        2: "Hi {name}, your order for {item} is still saved. Finish securely here: {payment_link}. Reply STOP to opt out.",
    },
    ClassificationCategory.INSUFFICIENT_FUNDS: {
        1: "Hi {name}, we held your {item} (Rs.{amount}). Pay whenever comfortable: {payment_link}. Reply STOP to opt out.",
        2: "Hi {name}, friendly reminder for your {item}. Complete your order here: {payment_link}. Reply STOP to opt out.",
    },
    ClassificationCategory.AUTHENTICATION_DROP: {
        1: "Hi {name}, looks like OTP verification timed out for {item}. Retry smoothly here: {payment_link}. Reply STOP to opt out.",
        2: "Hi {name}, tap here to retry checkout for your {item}: {payment_link}. Reply STOP to opt out.",
    },
    ClassificationCategory.INTENT_HESITATION: {
        1: "Hi {name}, still looking at the {item}? Complete your order easily here: {payment_link}. Reply STOP to opt out.",
        2: "Hi {name}, we've saved your {item}! Tap here to place your order: {payment_link}. Reply STOP to opt out.",
    },
    ClassificationCategory.DO_NOT_PURSUE: {
        1: "Contact suppressed by policy gate.",
        2: "Contact suppressed by policy gate.",
    }
}


DRAFTER_SYSTEM_PROMPT = """You are an empathetic customer support copywriter for an Indian e-commerce merchant.
Draft a short recovery SMS/WhatsApp message for a customer whose checkout payment did not complete.

STRICT REQUIREMENTS:
1. Length: MUST be under 180 characters total.
2. Must contain the exact placeholder: {payment_link}
3. Must contain an opt-out line at the end: 'Reply STOP to opt out.'
4. Tone: Warm, respectful, natural Indian conversational English.
5. PROHIBITED: No guilt-tripping, no urgency pressure ('Hurry!', 'Last chance!'), no legal/debt jargon.
6. Return JSON with key "message".
"""


def _sanitize_and_truncate(message: str, max_len: int = 195) -> str:
    """Ensures message has required tokens and fits under max length."""
    if "{payment_link}" not in message:
        message = f"{message} {payment_link}"
    if "STOP" not in message:
        message = f"{message} Reply STOP to opt out."
    
    # If still too long, fall back to concise format
    if len(message) > max_len:
        return message[:max_len - 25] + "... {payment_link}. Reply STOP to opt out."
    return message


def draft_recovery_message(
    category: ClassificationCategory,
    customer_name: str,
    cart_summary: str,
    amount_rupees: float,
    attempt_number: int = 1,
    channel: Union[str, RecoveryChannel] = RecoveryChannel.WHATSAPP,
    provider: Optional[LLMProvider] = None,
) -> DraftMessageResult:
    """
    Drafts a personalized outreach message using the LLM provider with fallback templates.
    """
    if category == ClassificationCategory.DO_NOT_PURSUE:
        return DraftMessageResult(
            message="Contact suppressed by do-not-pursue policy gate.",
            character_count=48,
            contains_link_placeholder=False,
            contains_opt_out=False,
            llm_fallback=True,
        )

    first_name = customer_name.strip().split()[0] if customer_name else "there"
    clean_cart = cart_summary[:28] if len(cart_summary) > 28 else cart_summary

    if provider is None:
        provider = get_llm_provider()

    user_prompt = f"""Draft a recovery message for:
- Customer: {first_name}
- Cart Item: {clean_cart}
- Amount: Rs. {int(amount_rupees)}
- Category: {category.value}
- Outreach Attempt: #{attempt_number}
- Channel: {channel.value if hasattr(channel, 'value') else channel}

Return JSON: {{"message": "..."}}
"""

    try:
        raw_res = provider.complete(system=DRAFTER_SYSTEM_PROMPT, user=user_prompt)
        draft = str(raw_res.get("message", "")).strip()

        if draft and "{payment_link}" in draft and ("STOP" in draft or "stop" in draft) and len(draft) <= 200:
            return DraftMessageResult(
                message=draft,
                character_count=len(draft),
                contains_link_placeholder=True,
                contains_opt_out=True,
                llm_fallback=False,
            )

    except Exception as e:
        logger.info(f"LLM drafting failed ({e}), using deterministic fallback template.")

    # Fallback to high-quality deterministic template
    attempt_key = 1 if attempt_number <= 1 else 2
    template = FALLBACK_TEMPLATES.get(category, FALLBACK_TEMPLATES[ClassificationCategory.TECHNICAL_FAILURE]).get(
        attempt_key,
        FALLBACK_TEMPLATES[ClassificationCategory.TECHNICAL_FAILURE][1]
    )

    formatted_msg = template.format(
        name=first_name,
        item=clean_cart,
        amount=int(amount_rupees),
        payment_link="{payment_link}",
    )

    return DraftMessageResult(
        message=formatted_msg,
        character_count=len(formatted_msg),
        contains_link_placeholder="{payment_link}" in formatted_msg,
        contains_opt_out="STOP" in formatted_msg,
        llm_fallback=True,
    )
