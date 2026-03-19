"""Notification service for customer communications.

Sends transactional emails for subscription events including
welcome messages, payment receipts, and trial expiry warnings.
"""

from __future__ import annotations

from datetime import datetime, timezone

# Send trial ending warning this many days before expiry
TRIAL_WARNING_DAYS_BEFORE = 3


def send_welcome_email(
    customer_email: str,
    customer_name: str,
    plan_name: str,
) -> dict[str, object]:
    """Send a welcome email to a new customer.

    Includes the plan name and a link to getting-started docs.

    Args:
        customer_email: Recipient email address.
        customer_name: Name for personalization.
        plan_name: The plan tier they signed up for.

    Returns:
        Notification result with status and timestamp.
    """
    return {
        "type": "welcome_email",
        "to": customer_email,
        "subject": f"Welcome to SubFlow, {customer_name}!",
        "plan": plan_name,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "status": "sent",
    }


def send_payment_receipt(
    customer_email: str,
    invoice_id: str,
    amount: float,
    payment_method: str,
) -> dict[str, object]:
    """Send a payment receipt after successful payment.

    Args:
        customer_email: Recipient email address.
        invoice_id: The paid invoice ID.
        amount: Payment amount in USD.
        payment_method: Method used (card, ach, wire).

    Returns:
        Notification result with status and timestamp.
    """
    return {
        "type": "payment_receipt",
        "to": customer_email,
        "subject": f"Payment receipt — ${amount:.2f}",
        "invoice_id": invoice_id,
        "amount": amount,
        "payment_method": payment_method,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "status": "sent",
    }


def send_trial_ending_warning(
    customer_email: str,
    customer_name: str,
    days_remaining: int,
    plan_name: str,
) -> dict[str, object] | None:
    """Send a trial ending warning if within the warning window.

    Only sends the notification if days_remaining is at or below
    TRIAL_WARNING_DAYS_BEFORE (3 days). Returns None if the warning
    window has not been reached yet.

    Args:
        customer_email: Recipient email address.
        customer_name: Name for personalization.
        days_remaining: Days left in the trial.
        plan_name: The current plan tier.

    Returns:
        Notification result, or None if not within warning window.
    """
    if days_remaining > TRIAL_WARNING_DAYS_BEFORE:
        return None

    return {
        "type": "trial_ending_warning",
        "to": customer_email,
        "subject": (
            f"{customer_name}, your SubFlow trial ends "
            f"in {days_remaining} day{'s' if days_remaining != 1 else ''}" 
        ),
        "days_remaining": days_remaining,
        "plan": plan_name,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "status": "sent",
    }


# Days after payment failure to send dunning emails
DUNNING_SCHEDULE_DAYS = [1, 3, 7, 14]

# Day threshold for escalation to account manager
ESCALATION_DAY = 7

# Auto-cancel subscription after this many days of non-payment
AUTO_CANCEL_DAYS = 21


def get_dunning_action(
    days_since_failure: int,
) -> dict[str, object]:
    """Determine the dunning action for a given day.

    Follows DUNNING_SCHEDULE_DAYS for email timing and
    escalates to account manager at ESCALATION_DAY (7).
    Auto-cancels at AUTO_CANCEL_DAYS (21).

    Args:
        days_since_failure: Days since the payment failure.

    Returns:
        Action dict with type and details.
    """
    if days_since_failure >= AUTO_CANCEL_DAYS:
        return {
            "action": "auto_cancel",
            "reason": (
                f"Non-payment for {days_since_failure} days "
                f"(limit: {AUTO_CANCEL_DAYS})"
            ),
        }

    should_send = days_since_failure in DUNNING_SCHEDULE_DAYS
    should_escalate = days_since_failure >= ESCALATION_DAY

    return {
        "action": "send_dunning" if should_send else "wait",
        "days_since_failure": days_since_failure,
        "escalate_to_am": should_escalate,
        "next_email_day": next(
            (d for d in DUNNING_SCHEDULE_DAYS
             if d > days_since_failure),
            None,
        ),
    }


def send_dunning_email(
    customer_email: str,
    customer_name: str,
    days_since_failure: int,
    invoice_id: str,
    amount_due: float,
) -> dict[str, object]:
    """Send a dunning email for a failed payment.

    Includes a link to update payment method and the
    outstanding amount.

    Args:
        customer_email: Recipient email address.
        customer_name: Name for personalization.
        days_since_failure: Days since the payment failure.
        invoice_id: The unpaid invoice ID.
        amount_due: Outstanding amount in USD.

    Returns:
        Notification result with status.
    """
    escalated = days_since_failure >= ESCALATION_DAY
    subject = (
        f"Action required: payment of ${amount_due:.2f} is overdue"
        if not escalated else
        f"URGENT: payment of ${amount_due:.2f} overdue — "
        f"account at risk of cancellation"
    )

    return {
        "type": "dunning_email",
        "to": customer_email,
        "subject": subject,
        "invoice_id": invoice_id,
        "amount_due": amount_due,
        "days_since_failure": days_since_failure,
        "escalated": escalated,
        "update_payment_link": f"/billing/update-payment?invoice={invoice_id}",
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "status": "sent",
    }


def send_suspension_notice(
    customer_email: str,
    customer_name: str,
    subscription_id: str,
    outstanding_balance: float,
    retention_days: int = 90,
) -> dict[str, object]:
    """Send a notification when an account is suspended.

    Informs the customer that their account has been suspended
    due to non-payment, includes the outstanding balance, and
    explains the data retention timeline.

    Args:
        customer_email: Recipient email address.
        customer_name: Name for personalization.
        subscription_id: The suspended subscription.
        outstanding_balance: Amount owed.
        retention_days: Days data will be retained.

    Returns:
        Notification result.
    """
    return {
        "type": "suspension_notice",
        "to": customer_email,
        "subject": (
            f"{customer_name}, your SubFlow account has been suspended"
        ),
        "subscription_id": subscription_id,
        "outstanding_balance": outstanding_balance,
        "retention_days": retention_days,
        "reactivation_link": f"/billing/reactivate?sub={subscription_id}",
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "status": "sent",
    }


def send_archival_warning(
    customer_email: str,
    customer_name: str,
    subscription_id: str,
    days_until_archival: int = 30,
) -> dict[str, object]:
    """Send a warning that account data will be archived soon.

    Sent at day 60 of suspension (30 days before the 90-day
    archival deadline).

    Args:
        customer_email: Recipient email address.
        customer_name: Name for personalization.
        subscription_id: The suspended subscription.
        days_until_archival: Days remaining before archival.

    Returns:
        Notification result.
    """
    return {
        "type": "archival_warning",
        "to": customer_email,
        "subject": (
            f"{customer_name}, your SubFlow data will be "
            f"archived in {days_until_archival} days"
        ),
        "subscription_id": subscription_id,
        "days_until_archival": days_until_archival,
        "reactivation_link": f"/billing/reactivate?sub={subscription_id}",
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "status": "sent",
    }


def send_archival_notice(
    customer_email: str,
    customer_name: str,
    subscription_id: str,
) -> dict[str, object]:
    """Send a notification that account data has been archived.

    Sent after the 90-day retention period expires and the
    account data has been archived.

    Args:
        customer_email: Recipient email address.
        customer_name: Name for personalization.
        subscription_id: The archived subscription.

    Returns:
        Notification result.
    """
    return {
        "type": "archival_notice",
        "to": customer_email,
        "subject": (
            f"{customer_name}, your SubFlow account data "
            "has been archived"
        ),
        "subscription_id": subscription_id,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "status": "sent",
    }
