"""Subscription analytics service.

Tracks key subscription metrics: MRR (monthly recurring
revenue), churn rate, and customer LTV (lifetime value).
Emits analytics events on subscription state changes.

Internal test accounts (subflow.dev, subflow-test.com) are
excluded from all metrics to prevent data skew.
"""

from __future__ import annotations

from datetime import datetime, timezone

# Email domains considered internal/test — excluded from metrics
INTERNAL_EMAIL_DOMAINS = ["subflow.dev", "subflow-test.com"]


def is_internal_account(email: str) -> bool:
    """Check whether an email belongs to an internal test account.

    Internal accounts (subflow.dev, subflow-test.com domains)
    are excluded from all analytics metrics.

    Args:
        email: The account email address.

    Returns:
        True if the email domain is in INTERNAL_EMAIL_DOMAINS.
    """
    domain = email.rsplit("@", 1)[-1].lower() if "@" in email else ""
    return domain in INTERNAL_EMAIL_DOMAINS


def calculate_mrr(
    subscriptions: list[dict],
) -> dict[str, object]:
    """Calculate monthly recurring revenue from active subscriptions.

    Only includes subscriptions with status "active" or "trial".
    Internal test accounts are excluded from the calculation.

    Args:
        subscriptions: List of subscription dicts with
            email, status, and monthly_price fields.

    Returns:
        MRR calculation with total, count, and breakdown.
    """
    total_mrr = 0.0
    included_count = 0
    excluded_count = 0

    for sub in subscriptions:
        if is_internal_account(sub.get("email", "")):
            excluded_count += 1
            continue
        if sub.get("status") in ("active", "trial"):
            total_mrr += sub.get("monthly_price", 0.0)
            included_count += 1

    return {
        "mrr": round(total_mrr, 2),
        "active_subscriptions": included_count,
        "excluded_internal": excluded_count,
    }


def calculate_churn_rate(
    total_start: int,
    churned: int,
    internal_churned: int = 0,
) -> dict[str, object]:
    """Calculate subscription churn rate for a period.

    Internal test accounts are excluded from both the
    numerator and denominator of the churn calculation.

    Args:
        total_start: Total subscriptions at period start.
        churned: Number of subscriptions cancelled in period.
        internal_churned: Number of internal account cancellations
            to exclude.

    Returns:
        Churn rate calculation details.
    """
    adjusted_total = total_start - internal_churned
    adjusted_churned = churned - internal_churned

    if adjusted_total <= 0:
        return {
            "churn_rate": 0.0,
            "churned": adjusted_churned,
            "total": adjusted_total,
        }

    rate = round((adjusted_churned / adjusted_total) * 100, 2)
    return {
        "churn_rate": rate,
        "churned": adjusted_churned,
        "total": adjusted_total,
        "excluded_internal": internal_churned,
    }


def calculate_ltv(
    customer_email: str,
    total_revenue: float,
    months_active: int,
) -> dict[str, object]:
    """Calculate lifetime value for a customer.

    Internal test accounts return an LTV of 0 since they
    are excluded from revenue metrics.

    Args:
        customer_email: The customer's email address.
        total_revenue: Total revenue from this customer.
        months_active: Number of months the customer has been active.

    Returns:
        LTV calculation with monthly average and total.
    """
    if is_internal_account(customer_email):
        return {
            "email": customer_email,
            "ltv": 0.0,
            "monthly_average": 0.0,
            "excluded": True,
            "reason": "Internal test account",
        }

    monthly_avg = (
        round(total_revenue / months_active, 2)
        if months_active > 0 else 0.0
    )

    return {
        "email": customer_email,
        "ltv": round(total_revenue, 2),
        "monthly_average": monthly_avg,
        "months_active": months_active,
        "excluded": False,
    }


def emit_analytics_event(
    event_type: str,
    subscription_id: str,
    customer_email: str,
    metadata: dict | None = None,
) -> dict[str, object]:
    """Emit an analytics event for a subscription state change.

    Events from internal test accounts are tagged but still
    emitted for debugging purposes. They are excluded from
    aggregate metric calculations.

    Args:
        event_type: The type of analytics event.
        subscription_id: The affected subscription.
        customer_email: The customer's email.
        metadata: Optional additional event data.

    Returns:
        The emitted event details.
    """
    now = datetime.now(timezone.utc)
    internal = is_internal_account(customer_email)

    return {
        "event_type": event_type,
        "subscription_id": subscription_id,
        "customer_email": customer_email,
        "is_internal": internal,
        "exclude_from_metrics": internal,
        "timestamp": now.isoformat(),
        "metadata": metadata or {},
    }
