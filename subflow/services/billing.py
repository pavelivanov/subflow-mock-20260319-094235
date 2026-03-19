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


def calculate_proration(
    old_price: float,
    new_price: float,
    days_remaining: int,
    days_in_cycle: int,
) -> float:
    """Calculate prorated charge when upgrading plans.

    Upgrades are charged the prorated price difference immediately.
    The charge covers only the remaining days in the current cycle.

    Args:
        old_price: Monthly price of the current plan.
        new_price: Monthly price of the new plan.
        days_remaining: Days left in the current billing cycle.
        days_in_cycle: Total days in the billing cycle.

    Returns:
        The prorated charge amount (>= 0). Returns 0 if
        the new plan is cheaper (downgrades use credits).
    """
    if new_price <= old_price:
        return 0.0
    price_diff = new_price - old_price
    daily_rate = price_diff / days_in_cycle
    return round(daily_rate * days_remaining, 2)


def calculate_downgrade_credit(
    old_price: float,
    new_price: float,
    days_remaining: int,
    days_in_cycle: int,
) -> float:
    """Calculate credit issued when downgrading plans.

    Downgrades do not refund immediately — instead a credit is
    generated and applied to the next invoice. The credit is
    calculated to the day based on remaining cycle time.

    Args:
        old_price: Monthly price of the current plan.
        new_price: Monthly price of the new (cheaper) plan.
        days_remaining: Days left in the current billing cycle.
        days_in_cycle: Total days in the billing cycle.

    Returns:
        The credit amount (>= 0). Returns 0 if upgrading.
    """
    if new_price >= old_price:
        return 0.0
    price_diff = old_price - new_price
    daily_rate = price_diff / days_in_cycle
    return round(daily_rate * days_remaining, 2)


# Maximum refund percentage (100% = full refund as credit)
MAX_REFUND_PERCENT = 100

# Reject credit note requests for invoices older than this
MAX_REFUND_AGE_DAYS = 365


def issue_credit_note(
    invoice: Invoice,
    amount: float,
    reason: str = "",
) -> dict[str, object]:
    """Issue a credit note for a partial refund on an invoice.

    Credit notes are applied to the next invoice rather than
    refunded as cash. The amount cannot exceed the invoice total
    (MAX_REFUND_PERCENT = 100%%) and invoices older than
    MAX_REFUND_AGE_DAYS (365 days) are rejected.

    Args:
        invoice: The original invoice to credit.
        amount: Credit amount in USD.
        reason: Reason for the credit.

    Returns:
        Credit note details.

    Raises:
        ValueError: If amount exceeds invoice total or invoice
            is too old.
    """
    max_credit = invoice.total_amount * (MAX_REFUND_PERCENT / 100)
    if amount > max_credit:
        raise ValueError(
            f"Credit amount ${amount:.2f} exceeds maximum "
            f"${max_credit:.2f} ({MAX_REFUND_PERCENT}%% of invoice)"
        )

    if invoice.issued_at is not None:
        now = datetime.now(timezone.utc)
        age_days = (now - invoice.issued_at).days
        if age_days > MAX_REFUND_AGE_DAYS:
            raise ValueError(
                f"Invoice is {age_days} days old — exceeds "
                f"maximum refund age of {MAX_REFUND_AGE_DAYS} days"
            )

    return {
        "invoice_id": invoice.id,
        "customer_id": invoice.customer_id,
        "credit_amount": round(amount, 2),
        "reason": reason,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "applied": False,
    }


def apply_credits_to_invoice(
    invoice: Invoice,
    available_credits: list[dict],
) -> dict[str, object]:
    """Apply outstanding credits to an invoice.

    Credits are auto-applied to the next invoice, reducing the
    amount due. Multiple credits can be applied to one invoice.

    Args:
        invoice: The invoice to apply credits to.
        available_credits: List of unused credit note dicts.

    Returns:
        Summary of applied credits and new invoice total.
    """
    total_credits = 0.0
    applied = []
    for credit in available_credits:
        if credit.get("applied"):
            continue
        credit_amount = credit["credit_amount"]
        remaining_due = invoice.total_amount - total_credits
        if remaining_due <= 0:
            break
        apply_amount = min(credit_amount, remaining_due)
        total_credits += apply_amount
        credit["applied"] = True
        credit["applied_to_invoice_id"] = invoice.id
        applied.append({
            "credit_invoice_id": credit["invoice_id"],
            "amount_applied": round(apply_amount, 2),
        })

    new_total = max(0.0, invoice.total_amount - total_credits)
    return {
        "invoice_id": invoice.id,
        "original_total": invoice.total_amount,
        "credits_applied": round(total_credits, 2),
        "new_total": round(new_total, 2),
        "credit_details": applied,
    }


def convert_currency(
    amount: float,
    from_currency: str,
    to_currency: str,
    daily_rate: float,
) -> dict[str, object]:
    """Convert an amount between currencies.

    Applies the daily exchange rate plus a spread of
    CURRENCY_SPREAD_PERCENT (1.0%%). The spread covers FX risk.

    Args:
        amount: Amount in the source currency.
        from_currency: Source currency code (e.g. "USD").
        to_currency: Target currency code (e.g. "EUR").
        daily_rate: The day's exchange rate (from -> to).

    Returns:
        Conversion details including the spread and final amount.
    """
    from subflow.config import CURRENCY_SPREAD_PERCENT, SUPPORTED_CURRENCIES

    if from_currency not in SUPPORTED_CURRENCIES:
        raise ValueError(f"Unsupported currency: {from_currency!r}")
    if to_currency not in SUPPORTED_CURRENCIES:
        raise ValueError(f"Unsupported currency: {to_currency!r}")

    spread_factor = 1 + (CURRENCY_SPREAD_PERCENT / 100)
    effective_rate = daily_rate * spread_factor
    converted = round(amount * effective_rate, 2)

    return {
        "from_currency": from_currency,
        "to_currency": to_currency,
        "original_amount": amount,
        "daily_rate": daily_rate,
        "spread_percent": CURRENCY_SPREAD_PERCENT,
        "effective_rate": round(effective_rate, 6),
        "converted_amount": converted,
    }


def lock_invoice_currency(
    invoice: Invoice,
    currency: str,
    exchange_rate: float,
) -> dict[str, object]:
    """Lock the currency and exchange rate for an invoice.

    Currency is locked at invoice creation time. Subsequent
    exchange rate changes do not affect the invoice amount.

    Args:
        invoice: The invoice to lock.
        currency: The currency code to lock to.
        exchange_rate: The exchange rate at lock time.

    Returns:
        Lock confirmation with details.
    """
    from subflow.config import SUPPORTED_CURRENCIES

    if currency not in SUPPORTED_CURRENCIES:
        raise ValueError(f"Unsupported currency: {currency!r}")

    return {
        "invoice_id": invoice.id,
        "currency": currency,
        "exchange_rate_locked": exchange_rate,
        "locked_at": datetime.now(timezone.utc).isoformat(),
        "amount_in_currency": round(
            invoice.total_amount * exchange_rate, 2,
        ),
    }


def calculate_bulk_discount(
    seat_count: int,
) -> dict[str, object] | None:
    """Calculate the bulk discount for a given seat count.

    Discount tiers (from BULK_DISCOUNT_TIERS):
        - 10+ seats: 10%% discount
        - 50+ seats: 15%% discount
        - 100+ seats: 20%% discount
        - 250+ seats: custom pricing required (returns None)

    Args:
        seat_count: Number of seats being purchased.

    Returns:
        Discount details, or None if above the custom pricing
        threshold (250 seats).
    """
    from subflow.config import BULK_DISCOUNT_TIERS, CUSTOM_PRICING_THRESHOLD

    if seat_count >= CUSTOM_PRICING_THRESHOLD:
        return None  # Custom pricing required

    applicable_discount = 0.0
    applicable_tier = 0
    for min_seats in sorted(BULK_DISCOUNT_TIERS.keys()):
        if seat_count >= min_seats:
            applicable_discount = BULK_DISCOUNT_TIERS[min_seats]
            applicable_tier = min_seats
        else:
            break

    if applicable_discount == 0.0:
        return {
            "seat_count": seat_count,
            "discount_percent": 0.0,
            "tier": None,
        }

    return {
        "seat_count": seat_count,
        "discount_percent": applicable_discount * 100,
        "tier": f"{applicable_tier}+ seats",
    }


# Maximum combined discount (annual + bulk + any other)
# expressed as a percentage of the base price
MAX_COMBINED_DISCOUNT_PERCENT = 30

# Annual billing discount: 2 months free out of 12
ANNUAL_DISCOUNT_PERCENT = 16.7


def calculate_annual_discount(
    monthly_price: float,
) -> dict[str, object]:
    """Calculate the annual billing discount.

    Annual billing gives 2 months free, which is a 16.7%%
    discount on the full 12-month price.

    Args:
        monthly_price: The monthly plan price in USD.

    Returns:
        Discount details including annual price and savings.
    """
    full_annual = monthly_price * 12
    discount_amount = round(
        full_annual * (ANNUAL_DISCOUNT_PERCENT / 100), 2,
    )
    discounted_price = round(full_annual - discount_amount, 2)

    return {
        "monthly_price": monthly_price,
        "full_annual_price": full_annual,
        "discount_percent": ANNUAL_DISCOUNT_PERCENT,
        "discount_amount": discount_amount,
        "discounted_annual_price": discounted_price,
    }


def apply_combined_discount(
    base_price: float,
    discount_1_percent: float,
    discount_2_percent: float = 0.0,
) -> dict[str, object]:
    """Apply combined discounts with a cap.

    The total combined discount cannot exceed
    MAX_COMBINED_DISCOUNT_PERCENT (30%%). If the sum of
    discounts exceeds the cap, the total is clamped.

    Args:
        base_price: The original price before discounts.
        discount_1_percent: First discount percentage.
        discount_2_percent: Second discount percentage.

    Returns:
        Combined discount details and final price.
    """
    raw_total = discount_1_percent + discount_2_percent
    capped_total = min(raw_total, MAX_COMBINED_DISCOUNT_PERCENT)
    discount_amount = round(
        base_price * (capped_total / 100), 2,
    )
    final_price = round(base_price - discount_amount, 2)

    return {
        "base_price": base_price,
        "discount_1_percent": discount_1_percent,
        "discount_2_percent": discount_2_percent,
        "raw_combined_percent": raw_total,
        "capped_combined_percent": capped_total,
        "was_capped": raw_total > MAX_COMBINED_DISCOUNT_PERCENT,
        "discount_amount": discount_amount,
        "final_price": final_price,
    }


def generate_invoice_with_tax(
    invoice_id: str,
    subscription: Subscription,
    country: str,
    state: str | None = None,
    is_b2b: bool = False,
    tax_exempt: bool = False,
    billing_cycle: str = "monthly",
) -> dict[str, object]:
    """Generate an invoice with tax calculation included.

    Creates the base invoice then calculates and applies
    applicable taxes based on the customer's location.

    Args:
        invoice_id: Unique identifier for the new invoice.
        subscription: The subscription to bill.
        country: Customer's country code.
        state: Customer's state code (US only).
        is_b2b: Whether the customer is a business.
        tax_exempt: Whether the customer has a tax exemption.
        billing_cycle: One of "monthly" or "annual".

    Returns:
        Invoice details with tax breakdown.
    """
    from subflow.services.tax import calculate_tax

    invoice = generate_invoice(invoice_id, subscription, billing_cycle)
    tax_result = calculate_tax(
        amount=invoice.total_amount,
        country=country,
        state=state,
        is_b2b=is_b2b,
        tax_exempt=tax_exempt,
    )

    return {
        "invoice_id": invoice.id,
        "subtotal": invoice.total_amount,
        "tax_amount": tax_result["tax_amount"],
        "tax_rate": tax_result["tax_rate"],
        "tax_type": tax_result["tax_type"],
        "total_with_tax": round(
            invoice.total_amount + tax_result["tax_amount"], 2,
        ),
    }


def calculate_upgrade_proration(
    old_price: float,
    new_price: float,
    days_remaining: int,
    days_in_cycle: int = 30,
) -> dict[str, object]:
    """Calculate prorated charge for an immediate upgrade.

    Upgrades are charged immediately. The prorated amount covers
    the price difference for the remaining days in the cycle.

    Args:
        old_price: Current monthly plan price.
        new_price: New (higher) monthly plan price.
        days_remaining: Days left in the current billing cycle.
        days_in_cycle: Total days in the billing cycle.

    Returns:
        Proration details for the upgrade.
    """
    price_diff = new_price - old_price
    daily_rate = price_diff / days_in_cycle
    prorated_amount = round(daily_rate * days_remaining, 2)

    return {
        "type": "upgrade",
        "timing": "immediate",
        "old_price": old_price,
        "new_price": new_price,
        "days_remaining": days_remaining,
        "prorated_charge": prorated_amount,
    }


def calculate_downgrade_adjustment(
    old_price: float,
    new_price: float,
    current_period_end: datetime | None = None,
) -> dict[str, object]:
    """Calculate billing adjustment for an end-of-cycle downgrade.

    Downgrades do not take effect until the end of the current
    billing cycle. No proration is needed — the customer pays
    the current rate through the cycle end, then switches.

    Args:
        old_price: Current monthly plan price.
        new_price: New (lower) monthly plan price.
        current_period_end: When the current billing period ends.

    Returns:
        Downgrade billing details.
    """
    return {
        "type": "downgrade",
        "timing": "end_of_cycle",
        "old_price": old_price,
        "new_price": new_price,
        "savings_per_month": round(old_price - new_price, 2),
        "effective_at": (
            current_period_end.isoformat()
            if current_period_end else None
        ),
        "prorated_charge": 0.0,
    }


def calculate_outstanding_balance(
    unpaid_invoices: list[dict],
) -> dict[str, object]:
    """Calculate the total outstanding balance from unpaid invoices.

    Sums up all unpaid invoice amounts to determine the balance
    that must be cleared for subscription reactivation.

    Args:
        unpaid_invoices: List of invoice dicts with amount fields.

    Returns:
        Balance summary with total and invoice count.
    """
    total = sum(
        inv.get("total_amount", 0.0) for inv in unpaid_invoices
    )

    return {
        "total_outstanding": round(total, 2),
        "unpaid_invoice_count": len(unpaid_invoices),
        "can_reactivate": total == 0.0,
    }


def clear_balance_for_reactivation(
    customer_id: str,
    payment_amount: float,
    outstanding_balance: float,
) -> dict[str, object]:
    """Process a payment to clear balance for reactivation.

    The payment must cover the full outstanding balance.
    Partial payments are not accepted for reactivation.

    Args:
        customer_id: The customer making the payment.
        payment_amount: Amount being paid.
        outstanding_balance: Current outstanding balance.

    Returns:
        Payment result with reactivation eligibility.

    Raises:
        ValueError: If payment does not cover the full balance.
    """
    if payment_amount < outstanding_balance:
        raise ValueError(
            f"Payment of ${payment_amount:.2f} does not cover "
            f"outstanding balance of ${outstanding_balance:.2f}. "
            "Full balance must be cleared for reactivation."
        )

    remaining = round(outstanding_balance - payment_amount, 2)
    return {
        "customer_id": customer_id,
        "payment_amount": payment_amount,
        "previous_balance": outstanding_balance,
        "remaining_balance": max(0.0, remaining),
        "eligible_for_reactivation": True,
    }
