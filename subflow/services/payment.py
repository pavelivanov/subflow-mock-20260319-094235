"""Payment processing service.

Handles payment method validation, processing fee calculation,
and payment execution. Fee structure varies by payment method type.
"""

from __future__ import annotations

from datetime import datetime, timezone

from subflow.models.invoice import Invoice

# Accepted payment method types
SUPPORTED_PAYMENT_METHODS = ["card", "ach", "wire"]

# Card processing fee: percentage component
CARD_PROCESSING_FEE_PERCENT = 2.9

# Card processing fee: fixed component per transaction (USD)
CARD_PROCESSING_FEE_FIXED = 0.30


def calculate_processing_fee(
    amount: float, method_type: str,
) -> float:
    """Calculate the processing fee for a payment.

    Fee structure:
        - card: 2.9%% + $0.30 per transaction
        - ach:  flat $1.00 per transaction
        - wire: no processing fee

    Args:
        amount: The payment amount in USD.
        method_type: One of card, ach, wire.

    Returns:
        The processing fee in USD.

    Raises:
        ValueError: If the payment method type is unsupported.
    """
    if method_type not in SUPPORTED_PAYMENT_METHODS:
        raise ValueError(
            f"Unsupported payment method: {method_type!r}. "
            f"Supported: {SUPPORTED_PAYMENT_METHODS}"
        )

    if method_type == "card":
        return round(
            amount * (CARD_PROCESSING_FEE_PERCENT / 100)
            + CARD_PROCESSING_FEE_FIXED,
            2,
        )
    elif method_type == "ach":
        return 1.00
    else:  # wire
        return 0.00


def process_payment(
    invoice: Invoice,
    method_type: str,
) -> dict[str, object]:
    """Process a payment for an invoice.

    Validates the payment method type, calculates fees, and marks
    the invoice as paid.

    Args:
        invoice: The invoice to pay.
        method_type: The payment method type.

    Returns:
        A dict with payment details including fee and net amount.

    Raises:
        ValueError: If invoice is already paid or amount is invalid.
    """
    if invoice.status == "paid":
        raise ValueError(
            f"Invoice {invoice.id} is already paid."
        )

    if invoice.total_amount <= 0:
        raise ValueError(
            f"Invoice amount must be positive, "
            f"got {invoice.total_amount}"
        )

    fee = calculate_processing_fee(invoice.total_amount, method_type)
    net_amount = invoice.total_amount - fee

    now = datetime.now(timezone.utc)
    invoice.status = "paid"
    invoice.paid_at = now

    return {
        "invoice_id": invoice.id,
        "gross_amount": invoice.total_amount,
        "processing_fee": fee,
        "net_amount": net_amount,
        "method_type": method_type,
        "paid_at": now.isoformat(),
    }
