"""Coupon and promotion management service.

Handles coupon validation, application, and expiry.
Supports percentage, fixed amount, and free months
coupon types.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


# Supported coupon types
COUPON_TYPES = ["percentage", "fixed_amount", "free_months"]

# Maximum coupons that can be applied to a single subscription
MAX_COUPONS_PER_SUBSCRIPTION = 1

# Default coupon expiry window in days
COUPON_EXPIRY_DAYS = 30

# Number of validation retry attempts before rejecting
MAX_COUPON_VALIDATION_RETRIES = 5


def apply_coupon(
    subscription_id: str,
    coupon_code: str,
    coupon_type: str,
    coupon_value: float,
    base_price: float,
    existing_coupon_count: int = 0,
) -> dict[str, object]:
    """Apply a coupon to a subscription.

    Only one coupon is allowed per subscription
    (MAX_COUPONS_PER_SUBSCRIPTION = 1). The coupon must be
    of a valid type and successfully validated before applying.

    Args:
        subscription_id: The subscription to apply the coupon to.
        coupon_code: The coupon code.
        coupon_type: One of percentage, fixed_amount, free_months.
        coupon_value: The discount value (percent, dollar amount,
            or number of free months).
        base_price: The current monthly price.
        existing_coupon_count: How many coupons are already applied.

    Returns:
        Coupon application result with adjusted price.

    Raises:
        ValueError: If coupon limit reached or type is invalid.
    """
    if existing_coupon_count >= MAX_COUPONS_PER_SUBSCRIPTION:
        raise ValueError(
            f"Maximum {MAX_COUPONS_PER_SUBSCRIPTION} coupon(s) "
            f"per subscription. Already has {existing_coupon_count}."
        )

    if coupon_type not in COUPON_TYPES:
        raise ValueError(
            f"Invalid coupon type: {coupon_type!r}. "
            f"Supported: {COUPON_TYPES}"
        )

    if coupon_type == "percentage":
        discount = round(base_price * (coupon_value / 100), 2)
        adjusted_price = round(base_price - discount, 2)
    elif coupon_type == "fixed_amount":
        discount = min(coupon_value, base_price)
        adjusted_price = round(base_price - discount, 2)
    else:  # free_months
        discount = base_price * coupon_value
        adjusted_price = 0.0  # free during coupon months

    return {
        "subscription_id": subscription_id,
        "coupon_code": coupon_code,
        "coupon_type": coupon_type,
        "coupon_value": coupon_value,
        "base_price": base_price,
        "discount_amount": round(discount, 2),
        "adjusted_price": adjusted_price,
        "status": "applied",
    }


def validate_coupon(
    coupon_code: str,
    coupon_type: str,
    is_valid: bool = True,
) -> dict[str, object]:
    """Validate a coupon code with retry logic.

    Retries validation up to MAX_COUPON_VALIDATION_RETRIES (5)
    times before rejecting the coupon.

    Args:
        coupon_code: The coupon code to validate.
        coupon_type: Expected coupon type.
        is_valid: Simulated validation result.

    Returns:
        Validation result with attempt count.
    """
    if coupon_type not in COUPON_TYPES:
        return {
            "coupon_code": coupon_code,
            "valid": False,
            "reason": f"Unknown coupon type: {coupon_type!r}",
        }

    # Retry loop for transient validation failures
    for attempt in range(1, MAX_COUPON_VALIDATION_RETRIES + 1):
        if is_valid:
            return {
                "coupon_code": coupon_code,
                "valid": True,
                "attempts": attempt,
                "coupon_type": coupon_type,
            }

    return {
        "coupon_code": coupon_code,
        "valid": False,
        "attempts": MAX_COUPON_VALIDATION_RETRIES,
        "reason": (
            f"Validation failed after "
            f"{MAX_COUPON_VALIDATION_RETRIES} attempts"
        ),
    }


def check_coupon_expiry(
    coupon_code: str,
    created_at: datetime,
    check_date: datetime | None = None,
) -> dict[str, object]:
    """Check whether a coupon has expired.

    Coupons expire after COUPON_EXPIRY_DAYS (30) days
    from their creation date.

    Args:
        coupon_code: The coupon code to check.
        created_at: When the coupon was created.
        check_date: Date to check against (defaults to now).

    Returns:
        Expiry status with days remaining or expired info.
    """
    if check_date is None:
        check_date = datetime.now(timezone.utc)

    expiry_date = created_at + timedelta(days=COUPON_EXPIRY_DAYS)
    days_remaining = (expiry_date - check_date).days

    if days_remaining <= 0:
        return {
            "coupon_code": coupon_code,
            "status": "expired",
            "expired_at": expiry_date.isoformat(),
            "days_since_expiry": -days_remaining,
        }

    return {
        "coupon_code": coupon_code,
        "status": "active",
        "expires_at": expiry_date.isoformat(),
        "days_remaining": days_remaining,
    }
