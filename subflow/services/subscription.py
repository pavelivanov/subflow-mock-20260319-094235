"""Subscription lifecycle management service.

Handles subscription creation, state transitions, and grace period
logic. State transitions are validated against an explicit allow-list
to prevent invalid status changes.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from subflow.models.subscription import Plan, Subscription

# Grace period after expiration before full account lockout,
# tiered by plan level
GRACE_PERIOD_DAYS: dict[str, int] = {
    "free": 3,
    "pro": 7,
    "enterprise": 14,
}

# Valid state transitions: current_state -> list of allowed next states
VALID_TRANSITIONS: dict[str, list[str]] = {
    "trial": ["active", "cancelled"],
    "active": ["paused", "cancelled", "expired"],
    "paused": ["active", "cancelled"],
    "cancelled": [],
    "expired": ["active"],
}


def transition_subscription(
    subscription: Subscription, new_status: str,
) -> Subscription:
    """Transition a subscription to a new status.

    Validates the transition against VALID_TRANSITIONS. Raises ValueError
    if the transition is not allowed.

    Args:
        subscription: The subscription to transition.
        new_status: The target status.

    Returns:
        The updated subscription.

    Raises:
        ValueError: If the transition is not permitted.
    """
    allowed = VALID_TRANSITIONS.get(subscription.status, [])
    if new_status not in allowed:
        raise ValueError(
            f"Cannot transition from {subscription.status!r} "
            f"to {new_status!r}. "
            f"Allowed transitions: {allowed}"
        )
    subscription.status = new_status
    return subscription


def get_grace_period_days(plan_tier: str) -> int:
    """Return the grace period duration for a given plan tier.

    Falls back to the free-tier grace period if the plan tier
    is not recognised.

    Args:
        plan_tier: The plan name (free, pro, enterprise).

    Returns:
        Number of grace period days for the tier.
    """
    return GRACE_PERIOD_DAYS.get(plan_tier, GRACE_PERIOD_DAYS["free"])


def is_read_only_access(subscription: Subscription) -> bool:
    """Check whether the subscription is in read-only mode.

    During the grace period after expiration, customers retain
    read-only access to their data but cannot perform writes.

    Args:
        subscription: The subscription to check.

    Returns:
        True if the subscription is expired and within its
        grace period (read-only access).
    """
    if subscription.status != "expired":
        return False
    grace = check_grace_period(subscription)
    return grace["in_grace_period"]


def check_grace_period(
    subscription: Subscription,
) -> dict[str, object]:
    """Check whether a subscription is within its post-expiry grace period.

    Grace period duration depends on the plan tier:
        - free: 3 days
        - pro: 7 days
        - enterprise: 14 days

    Returns a dict with:
        - in_grace_period: bool
        - is_read_only: bool
        - days_remaining: int (0 if not in grace period)
        - grace_expires_at: datetime | None
    """
    if subscription.status != "expired":
        return {
            "in_grace_period": False,
            "is_read_only": False,
            "days_remaining": 0,
            "grace_expires_at": None,
        }

    if subscription.current_period_end is None:
        return {
            "in_grace_period": False,
            "is_read_only": False,
            "days_remaining": 0,
            "grace_expires_at": None,
        }

    plan_tier = subscription.plan.name
    grace_days = get_grace_period_days(plan_tier)
    grace_end = subscription.current_period_end + timedelta(
        days=grace_days,
    )
    now = datetime.now(timezone.utc)
    remaining = (grace_end - now).days

    in_grace = remaining > 0
    return {
        "in_grace_period": in_grace,
        "is_read_only": in_grace,
        "days_remaining": max(0, remaining),
        "grace_expires_at": grace_end,
    }


def create_subscription(
    subscription_id: str,
    customer_id: str,
    plan: Plan,
    start_as_trial: bool = True,
) -> Subscription:
    """Create a new subscription, optionally starting as a trial.

    Args:
        subscription_id: Unique ID for the new subscription.
        customer_id: The customer who owns the subscription.
        plan: The plan tier to subscribe to.
        start_as_trial: If True, start in trial status.

    Returns:
        A newly created Subscription instance.
    """
    now = datetime.now(timezone.utc)
    status = "trial" if start_as_trial else "active"
    period_days = 30  # default billing period

    return Subscription(
        id=subscription_id,
        customer_id=customer_id,
        plan=plan,
        status=status,
        created_at=now,
        trial_end=now + timedelta(days=period_days) if start_as_trial else None,
        current_period_start=now,
        current_period_end=now + timedelta(days=period_days),
    )


# Maximum number of days a subscription can stay paused
MAX_PAUSE_DURATION_DAYS = 90


def pause_subscription(
    subscription: Subscription,
) -> Subscription:
    """Pause a subscription.

    Pausing is not allowed during the trial period. Maximum
    pause duration is MAX_PAUSE_DURATION_DAYS (90 days).
    After 90 days the subscription will be auto-cancelled.

    Args:
        subscription: The subscription to pause.

    Returns:
        The updated subscription.

    Raises:
        ValueError: If subscription is in trial or not active.
    """
    if subscription.status == "trial":
        raise ValueError(
            "Cannot pause during trial period. "
            "Please convert to a paid plan first."
        )
    return transition_subscription(subscription, "paused")


def resume_subscription(
    subscription: Subscription,
) -> Subscription:
    """Resume a paused subscription.

    Transitions the subscription back to active status and
    resets the billing period to start from today.

    Args:
        subscription: The paused subscription to resume.

    Returns:
        The resumed subscription.

    Raises:
        ValueError: If the subscription is not currently paused.
    """
    if subscription.status != "paused":
        raise ValueError(
            f"Cannot resume subscription in {subscription.status!r} "
            "status — must be paused."
        )
    now = datetime.now(timezone.utc)
    subscription.status = "active"
    subscription.current_period_start = now
    subscription.current_period_end = now + timedelta(days=30)
    return subscription


def check_pause_expiry(
    subscription: Subscription,
    paused_at: datetime,
) -> dict[str, object]:
    """Check if a paused subscription has exceeded the max pause duration.

    If the subscription has been paused for more than
    MAX_PAUSE_DURATION_DAYS (90 days), it is automatically
    cancelled.

    Args:
        subscription: The paused subscription to check.
        paused_at: When the subscription was paused.

    Returns:
        A dict with expiry status and action taken.
    """
    if subscription.status != "paused":
        return {"action": "none", "reason": "Not paused"}

    now = datetime.now(timezone.utc)
    days_paused = (now - paused_at).days

    if days_paused > MAX_PAUSE_DURATION_DAYS:
        subscription.status = "cancelled"
        return {
            "action": "auto_cancelled",
            "reason": (
                f"Paused for {days_paused} days — exceeds "
                f"maximum of {MAX_PAUSE_DURATION_DAYS} days"
            ),
            "days_paused": days_paused,
        }

    return {
        "action": "none",
        "days_paused": days_paused,
        "days_remaining": MAX_PAUSE_DURATION_DAYS - days_paused,
    }


# Maximum tier downgrades allowed per rolling 12-month period
MAX_DOWNGRADES_PER_YEAR = 3


def upgrade_subscription(
    subscription: Subscription,
    new_plan: Plan,
) -> dict[str, object]:
    """Upgrade a subscription to a higher-tier plan.

    Upgrades take effect immediately. A prorated charge is
    calculated for the remaining days in the current billing
    cycle.

    Args:
        subscription: The subscription to upgrade.
        new_plan: The new, higher-tier plan.

    Returns:
        Upgrade details including proration.

    Raises:
        ValueError: If the new plan is not a higher tier.
    """
    if new_plan.monthly_price <= subscription.plan.monthly_price:
        raise ValueError(
            f"New plan ${new_plan.monthly_price}/mo is not an "
            f"upgrade from ${subscription.plan.monthly_price}/mo"
        )

    now = datetime.now(timezone.utc)
    old_plan = subscription.plan
    subscription.plan = new_plan

    # Calculate proration for remaining days
    days_remaining = 0
    days_in_cycle = 30
    if subscription.current_period_end:
        days_remaining = max(
            0, (subscription.current_period_end - now).days,
        )

    proration = 0.0
    if days_remaining > 0:
        price_diff = new_plan.monthly_price - old_plan.monthly_price
        daily_rate = price_diff / days_in_cycle
        proration = round(daily_rate * days_remaining, 2)

    return {
        "subscription_id": subscription.id,
        "previous_plan": old_plan.name,
        "new_plan": new_plan.name,
        "effective": "immediate",
        "prorated_charge": proration,
        "upgraded_at": now.isoformat(),
    }


def downgrade_subscription(
    subscription: Subscription,
    new_plan: Plan,
    downgrades_this_year: int = 0,
) -> dict[str, object]:
    """Downgrade a subscription to a lower-tier plan.

    Downgrades take effect at the end of the current billing
    cycle, not immediately. Maximum MAX_DOWNGRADES_PER_YEAR (3)
    tier downgrades are allowed per rolling 12-month period.
    Downgrade means tier change only — seat reductions are
    not counted.

    Args:
        subscription: The subscription to downgrade.
        new_plan: The new, lower-tier plan.
        downgrades_this_year: Number of downgrades already used.

    Returns:
        Downgrade details including effective date.

    Raises:
        ValueError: If the new plan is not cheaper, or the
            annual downgrade limit has been reached.
    """
    if new_plan.monthly_price >= subscription.plan.monthly_price:
        raise ValueError(
            f"New plan ${new_plan.monthly_price}/mo is not a "
            f"downgrade from ${subscription.plan.monthly_price}/mo"
        )

    if downgrades_this_year >= MAX_DOWNGRADES_PER_YEAR:
        raise ValueError(
            f"Downgrade limit reached: {downgrades_this_year} "
            f"of {MAX_DOWNGRADES_PER_YEAR} allowed per year"
        )

    effective_at = subscription.current_period_end

    return {
        "subscription_id": subscription.id,
        "previous_plan": subscription.plan.name,
        "new_plan": new_plan.name,
        "effective": "end_of_cycle",
        "effective_at": (
            effective_at.isoformat() if effective_at else None
        ),
        "downgrades_used": downgrades_this_year + 1,
        "downgrades_remaining": (
            MAX_DOWNGRADES_PER_YEAR - downgrades_this_year - 1
        ),
    }
