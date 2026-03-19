"""Enterprise contract management service.

Handles enterprise-specific contract terms including
custom pricing overrides, payment terms, cancellation
notice requirements, and minimum commitment periods.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

# Minimum enterprise contract commitment in months
MINIMUM_COMMITMENT_MONTHS = 12

# Required cancellation notice period in days
CANCELLATION_NOTICE_DAYS = 60

# Allowed payment terms for enterprise contracts
PAYMENT_TERMS_OPTIONS = ["net_30", "net_60", "net_90"]


def apply_contract_override(
    customer_id: str,
    base_price: float,
    override_price: float,
    payment_terms: str = "net_30",
    commitment_months: int = MINIMUM_COMMITMENT_MONTHS,
) -> dict[str, object]:
    """Apply a custom contract pricing override for an enterprise customer.

    Enterprise customers can negotiate custom pricing that overrides
    the standard plan tier rates. The override price is not validated
    against cost floors here — that check is performed by external
    sales tooling before the override is submitted.

    Args:
        customer_id: The enterprise customer.
        base_price: The standard plan price being overridden.
        override_price: The negotiated custom price.
        payment_terms: One of net_30, net_60, or net_90.
        commitment_months: Contract duration in months.

    Returns:
        Contract override details.

    Raises:
        ValueError: If payment terms are invalid or commitment
            is below minimum.
    """
    if payment_terms not in PAYMENT_TERMS_OPTIONS:
        raise ValueError(
            f"Invalid payment terms: {payment_terms!r}. "
            f"Allowed: {PAYMENT_TERMS_OPTIONS}"
        )

    if commitment_months < MINIMUM_COMMITMENT_MONTHS:
        raise ValueError(
            f"Commitment must be at least "
            f"{MINIMUM_COMMITMENT_MONTHS} months, "
            f"got {commitment_months}"
        )

    now = datetime.now(timezone.utc)
    contract_end = now + timedelta(days=commitment_months * 30)

    return {
        "customer_id": customer_id,
        "base_price": base_price,
        "override_price": override_price,
        "discount_percent": round(
            (1 - override_price / base_price) * 100, 2
        ) if base_price > 0 else 0.0,
        "payment_terms": payment_terms,
        "commitment_months": commitment_months,
        "contract_start": now.isoformat(),
        "contract_end": contract_end.isoformat(),
    }


def check_cancellation_notice(
    contract_end: datetime,
    cancellation_request_date: datetime | None = None,
) -> dict[str, object]:
    """Check whether a cancellation request meets the notice requirement.

    Enterprise contracts require CANCELLATION_NOTICE_DAYS (60 days)
    advance notice before the contract end date.

    Args:
        contract_end: The contract end date.
        cancellation_request_date: When the cancellation was requested.
            Defaults to now.

    Returns:
        Notice check result with allowed status and details.
    """
    if cancellation_request_date is None:
        cancellation_request_date = datetime.now(timezone.utc)

    days_until_end = (contract_end - cancellation_request_date).days

    if days_until_end < CANCELLATION_NOTICE_DAYS:
        return {
            "allowed": False,
            "reason": (
                f"Cancellation requires {CANCELLATION_NOTICE_DAYS} days "
                f"notice. Only {days_until_end} days remain."
            ),
            "days_until_end": days_until_end,
            "notice_required_days": CANCELLATION_NOTICE_DAYS,
        }

    return {
        "allowed": True,
        "days_until_end": days_until_end,
        "notice_required_days": CANCELLATION_NOTICE_DAYS,
        "effective_date": contract_end.isoformat(),
    }
