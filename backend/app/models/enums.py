from enum import Enum


class PropensityProfile(str, Enum):
    """
    CRITICAL ARCHITECTURAL BOUNDARY:
    This enum represents the customer's true underlying psychological propensity to pay.
    It is PRIVATE GROUND TRUTH for the simulation engine only.

    WHY THIS MUST REMAIN INVISIBLE TO THE AGENT:
    In real-world e-commerce, a merchant never knows the buyer's private mental state with certainty.
    If the recovery agent had access to `propensity_profile`, it would suffer from severe 'data leakage'
    (cheating), learning artificial shortcuts instead of deriving intelligence from observable signals
    (e.g., specific error codes, past transaction failure rates, cart value, and session timing).
    """
    RELIABLE = "reliable"       # High willingness, failed due to transient glitch
    DISTRACTED = "distracted"   # Abandoned due to interruption, high recovery on nudge
    HESITANT = "hesitant"       # Price-sensitive, second-guessing purchase
    BROKE = "broke"             # True liquidity constraint (insufficient funds)
    GHOST = "ghost"             # Deliberate bounce/fake intent, will not recover


class PaymentMethod(str, Enum):
    UPI = "upi"
    CARD = "card"
    NETBANKING = "netbanking"
    WALLET = "wallet"


class PaymentStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RECOVERED = "recovered"
    ABANDONED = "abandoned"
    SUPPRESSED = "suppressed"


class RecoveryChannel(str, Enum):
    WHATSAPP = "whatsapp"
    SMS = "sms"
    EMAIL = "email"
    IVR = "ivr"


class RecoveryAction(str, Enum):
    PAYMENT_LINK = "send_payment_link"
    DISCOUNT_NUDGE = "send_discount_nudge"
    PAYMENT_REMINDER = "payment_reminder"
    SUPPRESS = "suppress_contact"


class AttemptOutcome(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    CLICKED = "clicked"
    IGNORED = "ignored"
    BOUNCED = "bounced"
    OPTED_OUT = "opted_out"


class DatasetSplit(str, Enum):
    TRAIN = "train"
    HELD_OUT = "held_out"
