"""Trial period management service.

Handles trial lifecycle: starting trials, checking status,
and converting trials to paid subscriptions. Enforces
payment method requirements before trial expiry.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from subflow.config import TRIAL_PERIOD_DAYS
from subflow.models.subscription import Subscription

# Payment method must be on file by this many days before trial end
PAYMENT_METHOD_REQUIRED_BY_DAY = 25


def start_trial(
    subscription: Subscription,
) -> Subscription:
    """Start a trial period for a subscription.

    Sets the subscription status to trial and calculates the
    trial end date based on TRIAL_PERIOD_DAYS.

    Args:
        subscription: The subscription to start trialing.

    Returns:
        The updated subscription with trial dates set.
    """
    now = datetime.now(timezone.utc)
    subscription.status = "trial"
    subscription.trial_end = now + timedelta(days=TRIAL_PERIOD_DAYS)
    subscription.current_period_start = now
    subscription.current_period_end = subscription.trial_end
    return subscription


def check_trial_status(
    subscription: Subscription,
    has_payment_method: bool = False,
) -> str:
    """Check the current trial status and determine next action.

    Returns one of:
        - "active": Trial is still running, no action needed.
        - "convert": Trial has ended, ready to convert to paid.
        - "needs_payment_method": Trial is nearing end and payment
          method is required before day PAYMENT_METHOD_REQUIRED_BY_DAY.

    Args:
        subscription: The subscription to check.
        has_payment_method: Whether the customer has a payment method.

    Returns:
        Status string indicating required action.
    """
    if subscription.status != "trial" or subscription.trial_end is None:
        return "active"

    now = datetime.now(timezone.utc)
    days_elapsed = (now - subscription.current_period_start).days

    # Trial has ended
    if now >= subscription.trial_end:
        return "convert"

    # Approaching trial end — payment method required
    if (
        days_elapsed >= PAYMENT_METHOD_REQUIRED_BY_DAY
        and not has_payment_method
    ):
        return "needs_payment_method"

    return "active"


def convert_trial_to_paid(
    subscription: Subscription,
    has_payment_method: bool,
) -> Subscription:
    """Convert a trial subscription to a paid active subscription.

    Requires a valid payment method on file. Sets the billing period
    to start from the conversion date.

    Args:
        subscription: The trial subscription to convert.
        has_payment_method: Whether the customer has a payment method.

    Returns:
        The converted subscription.

    Raises:
        ValueError: If no payment method or subscription is not in trial.
    """
    if subscription.status != "trial":
        raise ValueError(
            f"Cannot convert subscription in {subscription.status!r} "
            "status — must be in trial."
        )
    if not has_payment_method:
        raise ValueError(
            "Payment method required to convert trial to paid."
        )

    now = datetime.now(timezone.utc)
    subscription.status = "active"
    subscription.trial_end = None
    subscription.current_period_start = now
    subscription.current_period_end = now + timedelta(days=30)
    return subscription
