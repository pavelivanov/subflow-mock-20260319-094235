"""Billing service for invoice generation and billing cycle management.

Generates invoices based on subscription plan pricing and manages
billing cycle date calculations.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from subflow.config import INVOICE_DUE_DAYS, PLAN_TIERS
from subflow.models.invoice import Invoice, LineItem
from subflow.models.subscription import Subscription


def generate_invoice(
    invoice_id: str,
    subscription: Subscription,
    billing_cycle: str = "monthly",
) -> Invoice:
    """Generate an invoice for the current billing period.

    Looks up the plan tier pricing from PLAN_TIERS and creates
    an invoice with the appropriate line items.

    Args:
        invoice_id: Unique identifier for the new invoice.
        subscription: The subscription to bill.
        billing_cycle: One of "monthly" or "annual".

    Returns:
        A new Invoice with line items and due date set.

    Raises:
        ValueError: If the plan tier is not found in PLAN_TIERS.
    """
    tier_name = subscription.plan.name
    tier = PLAN_TIERS.get(tier_name)
    if tier is None:
        raise ValueError(f"Unknown plan tier: {tier_name!r}")

    monthly_price = tier["monthly_price"]

    if billing_cycle == "annual":
        # Annual billing: 10 months price (2 months free)
        amount = monthly_price * 10
        description = f"{tier_name.title()} Plan — Annual"
    else:
        amount = monthly_price
        description = f"{tier_name.title()} Plan — Monthly"

    now = datetime.now(timezone.utc)
    line_items = [
        LineItem(
            description=description,
            quantity=1,
            unit_price=float(amount),
        ),
    ]

    invoice = Invoice(
        id=invoice_id,
        subscription_id=subscription.id,
        customer_id=subscription.customer_id,
        status="issued",
        line_items=line_items,
        issued_at=now,
        due_at=now + timedelta(days=INVOICE_DUE_DAYS),
    )
    invoice.calculate_total()
    return invoice


def calculate_next_billing_date(
    current_period_end: datetime,
    billing_cycle: str = "monthly",
) -> datetime:
    """Calculate the next billing date based on cycle type.

    Monthly cycles advance by 30 days, annual by 365 days.

    Args:
        current_period_end: End of the current billing period.
        billing_cycle: One of "monthly" or "annual".

    Returns:
        The next billing date.
    """
    if billing_cycle == "annual":
        return current_period_end + timedelta(days=365)
    return current_period_end + timedelta(days=30)
