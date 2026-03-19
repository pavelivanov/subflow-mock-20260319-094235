"""Referral program service.

Manages customer referral credits, validation, and tracking.
Referrers earn a percentage credit on referred subscriptions,
and referred customers get free months.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

# Referrer gets this percentage of the referred subscription price
REFERRAL_CREDIT_PERCENT = 20

# Maximum credit per single referral (USD)
MAX_REFERRAL_CREDIT = 50.00

# Maximum total referral credits per year (USD)
MAX_ANNUAL_REFERRAL_CREDIT = 500.00

# Referral links expire after this many days
REFERRAL_VALIDITY_DAYS = 90

# Referred customer gets this many months free
REFEREE_FREE_MONTHS = 1


def create_referral(
    referrer_id: str,
) -> dict[str, object]:
    """Create a new referral link for a customer.

    The referral link is valid for REFERRAL_VALIDITY_DAYS (90 days).

    Args:
        referrer_id: The customer creating the referral.

    Returns:
        Referral details including code and expiry.
    """
    now = datetime.now(timezone.utc)
    return {
        "referrer_id": referrer_id,
        "referral_code": f"REF-{referrer_id[:8].upper()}",
        "created_at": now.isoformat(),
        "expires_at": (
            now + timedelta(days=REFERRAL_VALIDITY_DAYS)
        ).isoformat(),
        "status": "active",
    }


def validate_referral(
    referral_code: str,
    referral_created_at: datetime,
) -> dict[str, object]:
    """Validate a referral code and check if it is still active.

    Args:
        referral_code: The referral code to validate.
        referral_created_at: When the referral was created.

    Returns:
        Validation result with valid flag and reason.
    """
    now = datetime.now(timezone.utc)
    expiry = referral_created_at + timedelta(
        days=REFERRAL_VALIDITY_DAYS,
    )
    if now > expiry:
        return {
            "valid": False,
            "reason": "Referral code has expired",
            "referral_code": referral_code,
        }
    return {
        "valid": True,
        "referral_code": referral_code,
        "expires_at": expiry.isoformat(),
    }


def apply_referral_credit(
    referrer_id: str,
    subscription_price: float,
    annual_credits_used: float = 0.0,
) -> dict[str, object]:
    """Calculate and apply referral credit for the referrer.

    Credit is REFERRAL_CREDIT_PERCENT (20%%) of the referred
    subscription price, capped at MAX_REFERRAL_CREDIT ($50)
    per referral and MAX_ANNUAL_REFERRAL_CREDIT ($500) per year.

    Args:
        referrer_id: The referring customer.
        subscription_price: Monthly price of the referred subscription.
        annual_credits_used: Credits already used this year.

    Returns:
        Credit details including amount and remaining annual limit.
    """
    raw_credit = subscription_price * (REFERRAL_CREDIT_PERCENT / 100)
    capped_credit = min(raw_credit, MAX_REFERRAL_CREDIT)

    annual_remaining = MAX_ANNUAL_REFERRAL_CREDIT - annual_credits_used
    final_credit = min(capped_credit, max(0.0, annual_remaining))

    return {
        "referrer_id": referrer_id,
        "credit_amount": round(final_credit, 2),
        "annual_credits_used": annual_credits_used + final_credit,
        "annual_remaining": round(
            annual_remaining - final_credit, 2,
        ),
    }
