"""Trial period management service.

Handles trial lifecycle: starting trials, checking status,
and converting trials to paid subscriptions. Enforces
payment method requirements before trial expiry.

Trial duration is now per-tier (Free=14d, Pro=30d, Enterprise=30d).
Includes trial abuse prevention: domain limits, disposable email
blocking, and card requirement for Free tier.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from subflow.config import (
    DISPOSABLE_EMAIL_DOMAINS,
    FREE_TRIAL_REQUIRES_CARD,
    MAX_TRIALS_PER_DOMAIN,
    TRIAL_DOMAIN_WINDOW_DAYS,
    TRIAL_PERIOD_DAYS,
)
from subflow.models.subscription import Subscription

# Payment method must be on file by this many days before trial end
PAYMENT_METHOD_REQUIRED_BY_DAY = 25


def get_trial_days(plan_tier: str) -> int:
    """Return the trial duration in days for the given plan tier.

    Handles both the legacy integer format and the current
    per-tier dict format of TRIAL_PERIOD_DAYS.

    Args:
        plan_tier: The plan tier name (free, pro, enterprise).

    Returns:
        Number of trial days for the given tier.
    """
    if isinstance(TRIAL_PERIOD_DAYS, dict):
        return TRIAL_PERIOD_DAYS.get(plan_tier, 14)
    return TRIAL_PERIOD_DAYS


def start_trial(
    subscription: Subscription,
) -> Subscription:
    """Start a trial period for a subscription.

    Sets the subscription status to trial and calculates the
    trial end date based on the plan tier's trial duration.

    Args:
        subscription: The subscription to start trialing.

    Returns:
        The updated subscription with trial dates set.
    """
    now = datetime.now(timezone.utc)
    trial_days = get_trial_days(subscription.plan.name)
    subscription.status = "trial"
    subscription.trial_end = now + timedelta(days=trial_days)
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
          method is required.

    Args:
        subscription: The subscription to check.
        has_payment_method: Whether the customer has a payment method.

    Returns:
        Status string indicating required action.
    """
    if subscription.status != "trial" or subscription.trial_end is None:
        return "active"

    now = datetime.now(timezone.utc)
    trial_days = get_trial_days(subscription.plan.name)
    days_elapsed = (now - subscription.current_period_start).days

    # Trial has ended
    if now >= subscription.trial_end:
        return "convert"

    # Approaching trial end — payment method required
    # For short trials (< 25 days), require payment by 80%% of trial
    payment_required_by = min(
        PAYMENT_METHOD_REQUIRED_BY_DAY,
        int(trial_days * 0.8),
    )
    if days_elapsed >= payment_required_by and not has_payment_method:
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


def check_trial_eligibility(
    email: str,
    plan_tier: str,
    domain_trials_in_window: int = 0,
    has_payment_card: bool = False,
) -> dict[str, object]:
    """Check whether a new trial is allowed for the given email.

    Enforces trial abuse prevention rules:
        - Max MAX_TRIALS_PER_DOMAIN (1) trial per email domain
          within TRIAL_DOMAIN_WINDOW_DAYS (90 days).
        - Disposable email domains are blocked.
        - Free tier trials require a payment card on file
          (FREE_TRIAL_REQUIRES_CARD = True).

    These rules apply to new trials only. Existing active
    trials are not affected.

    Args:
        email: The customer's email address.
        plan_tier: The plan tier for the trial.
        domain_trials_in_window: Number of trials from this
            email domain in the last TRIAL_DOMAIN_WINDOW_DAYS days.
        has_payment_card: Whether the customer has a card on file.

    Returns:
        Eligibility result with allowed status and reason.
    """
    domain = email.rsplit("@", 1)[-1].lower() if "@" in email else ""

    # Check disposable email
    if domain in DISPOSABLE_EMAIL_DOMAINS:
        return {
            "eligible": False,
            "reason": "Disposable email domains are not allowed",
            "email": email,
            "domain": domain,
        }

    # Check domain trial limit
    if domain_trials_in_window >= MAX_TRIALS_PER_DOMAIN:
        return {
            "eligible": False,
            "reason": (
                f"Domain {domain!r} has reached the limit of "
                f"{MAX_TRIALS_PER_DOMAIN} trial(s) per "
                f"{TRIAL_DOMAIN_WINDOW_DAYS} days"
            ),
            "email": email,
            "domain": domain,
        }

    # Check card requirement for Free tier
    if (
        plan_tier == "free"
        and FREE_TRIAL_REQUIRES_CARD
        and not has_payment_card
    ):
        return {
            "eligible": False,
            "reason": "Free tier trial requires a payment card on file",
            "email": email,
            "plan_tier": plan_tier,
        }

    return {
        "eligible": True,
        "email": email,
        "plan_tier": plan_tier,
        "domain": domain,
    }
