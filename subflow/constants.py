"""Shared constants and status enums for the SubFlow platform.

Centralizes all status values and failure codes as enums to
prevent string typos and enable IDE autocompletion.
"""

from enum import Enum


class SubscriptionStatus(str, Enum):
    """Possible states for a subscription."""

    TRIAL = "trial"
    ACTIVE = "active"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    SUSPENDED = "suspended"


class InvoiceStatus(str, Enum):
    """Possible states for an invoice."""

    DRAFT = "draft"
    ISSUED = "issued"
    PAID = "paid"
    OVERDUE = "overdue"
    VOID = "void"
    REFUNDED = "refunded"


class PaymentFailureCode(str, Enum):
    """Standardized payment failure reason codes."""

    INSUFFICIENT_FUNDS = "insufficient_funds"
    CARD_DECLINED = "card_declined"
    CARD_EXPIRED = "card_expired"
    FRAUD_DETECTED = "fraud_detected"
    PROCESSING_ERROR = "processing_error"
    INVALID_ACCOUNT = "invalid_account"
