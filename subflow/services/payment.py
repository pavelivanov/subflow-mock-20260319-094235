"""Payment processing service.

Handles payment method validation, processing fee calculation,
payment execution, and basic fraud detection. Fee structure
varies by payment method type.
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

# Fraud prevention thresholds
MAX_SINGLE_TRANSACTION_AMOUNT = 10_000
MAX_FAILED_PAYMENTS_24H = 3


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


def check_fraud_risk(
    amount: float,
    failed_payments_24h: int = 0,
    customer_age_days: int = 0,
) -> dict[str, object]:
    """Evaluate fraud risk for a payment attempt.

    Checks multiple fraud indicators:
        - Single transaction exceeds MAX_SINGLE_TRANSACTION_AMOUNT
        - Too many failed payments in 24 hours
        - New account making large payments (< 7 days old, > $1000)

    Args:
        amount: The payment amount in USD.
        failed_payments_24h: Number of failed payment attempts
            in the last 24 hours for this customer.
        customer_age_days: How many days since the customer account
            was created.

    Returns:
        A dict with:
            - approved: bool — whether the payment should proceed.
            - risk_flags: list[str] — reasons for flagging.
            - risk_score: int — 0 (safe) to 100 (definite fraud).
    """
    risk_flags: list[str] = []
    risk_score = 0

    # Check 1: Transaction amount exceeds single-transaction limit
    if amount > MAX_SINGLE_TRANSACTION_AMOUNT:
        risk_flags.append(
            f"Amount ${amount:.2f} exceeds single-transaction "
            f"limit of ${MAX_SINGLE_TRANSACTION_AMOUNT}"
        )
        risk_score += 40

    # Check 2: Too many failed payments in 24 hours
    if failed_payments_24h >= MAX_FAILED_PAYMENTS_24H:
        risk_flags.append(
            f"{failed_payments_24h} failed payments in 24h "
            f"(limit: {MAX_FAILED_PAYMENTS_24H})"
        )
        risk_score += 35

    # Check 3: New account making large payment
    if customer_age_days < 7 and amount > 1000:
        risk_flags.append(
            f"New account ({customer_age_days}d old) "
            f"attempting payment of ${amount:.2f}"
        )
        risk_score += 25

    return {
        "approved": risk_score < 50,
        "risk_flags": risk_flags,
        "risk_score": min(risk_score, 100),
    }


def process_payment(
    invoice: Invoice,
    method_type: str,
    failed_payments_24h: int = 0,
    customer_age_days: int = 365,
) -> dict[str, object]:
    """Process a payment for an invoice.

    Validates the payment method type, runs fraud checks,
    calculates fees, and marks the invoice as paid.

    Args:
        invoice: The invoice to pay.
        method_type: The payment method type.
        failed_payments_24h: Recent failed payment count.
        customer_age_days: Customer account age in days.

    Returns:
        A dict with payment details including fee and net amount.

    Raises:
        ValueError: If invoice is already paid, amount is invalid,
            or fraud check fails.
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

    # Run fraud checks before processing
    fraud_result = check_fraud_risk(
        amount=invoice.total_amount,
        failed_payments_24h=failed_payments_24h,
        customer_age_days=customer_age_days,
    )
    if not fraud_result["approved"]:
        raise ValueError(
            f"Payment blocked by fraud check: "
            f"{fraud_result['risk_flags']}"
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
        "fraud_check": fraud_result,
    }


# Retry schedule: hours after initial failure
RETRY_SCHEDULE_HOURS = [1, 24, 72, 168]

# Maximum number of retry attempts before suspension
MAX_RETRIES = 4


def schedule_retry(
    invoice_id: str,
    attempt_number: int,
) -> dict[str, object]:
    """Schedule a payment retry based on the attempt number.

    Retries follow RETRY_SCHEDULE_HOURS: 1h, 24h, 72h, 168h
    after the initial failure.

    Args:
        invoice_id: The invoice that failed payment.
        attempt_number: Which retry attempt this is (1-based).

    Returns:
        A dict with retry_at (hours from now) and attempt info.
        Returns None-like dict if max retries exceeded.
    """
    if attempt_number > MAX_RETRIES:
        return {
            "invoice_id": invoice_id,
            "action": "suspend",
            "reason": f"Exceeded {MAX_RETRIES} retry attempts",
        }

    hours = RETRY_SCHEDULE_HOURS[attempt_number - 1]
    return {
        "invoice_id": invoice_id,
        "action": "retry",
        "attempt": attempt_number,
        "retry_after_hours": hours,
    }


def process_retry(
    invoice: Invoice,
    method_type: str,
    attempt_number: int,
    failed_payments_24h: int = 0,
    customer_age_days: int = 365,
) -> dict[str, object]:
    """Attempt a payment retry for a failed invoice.

    If the retry fails and max retries are exceeded, triggers
    subscription suspension. After 4 failed attempts the
    subscription is suspended.

    Args:
        invoice: The invoice to retry payment for.
        method_type: The payment method type.
        attempt_number: Current retry attempt (1-based).
        failed_payments_24h: Recent failed payment count.
        customer_age_days: Customer account age in days.

    Returns:
        A dict with the retry result or suspension trigger.
    """
    try:
        result = process_payment(
            invoice, method_type,
            failed_payments_24h=failed_payments_24h,
            customer_age_days=customer_age_days,
        )
        result["retry_attempt"] = attempt_number
        result["action"] = "paid"
        return result
    except ValueError:
        if attempt_number >= MAX_RETRIES:
            return {
                "invoice_id": invoice.id,
                "action": "suspend",
                "reason": (
                    f"Payment failed after {MAX_RETRIES} "
                    "retries — suspending subscription"
                ),
                "attempt": attempt_number,
            }
        return schedule_retry(invoice.id, attempt_number + 1)
