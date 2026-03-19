"""Subscription lifecycle management service.

Handles subscription creation, state transitions, and grace period
logic. State transitions are validated against an explicit allow-list
to prevent invalid status changes.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from subflow.models.subscription import Plan, Subscription

# Grace period after expiration before full account lockout
GRACE_PERIOD_DAYS = 7

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


def check_grace_period(
    subscription: Subscription,
) -> dict[str, object]:
    """Check whether a subscription is within its post-expiry grace period.

    Returns a dict with:
        - in_grace_period: bool
        - days_remaining: int (0 if not in grace period)
        - grace_expires_at: datetime | None
    """
    if subscription.status != "expired":
        return {
            "in_grace_period": False,
            "days_remaining": 0,
            "grace_expires_at": None,
        }

    if subscription.current_period_end is None:
        return {
            "in_grace_period": False,
            "days_remaining": 0,
            "grace_expires_at": None,
        }

    grace_end = subscription.current_period_end + timedelta(
        days=GRACE_PERIOD_DAYS,
    )
    now = datetime.now(timezone.utc)
    remaining = (grace_end - now).days

    return {
        "in_grace_period": remaining > 0,
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
