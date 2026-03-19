"""API route definitions for the SubFlow platform.

Defines endpoint handlers for subscription management,
billing, webhook registration, and customer operations.
These are framework-agnostic handler functions (not tied
to Flask/FastAPI).
"""

from __future__ import annotations

from subflow.services.webhook import WEBHOOK_EVENTS


def create_subscription_endpoint(
    customer_id: str, plan_tier: str,
) -> dict[str, object]:
    """Handle POST /subscriptions — create a new subscription.

    Args:
        customer_id: The customer requesting a subscription.
        plan_tier: The desired plan tier.

    Returns:
        Response dict with subscription details.
    """
    return {
        "status": "created",
        "customer_id": customer_id,
        "plan_tier": plan_tier,
    }


def get_subscription_endpoint(
    subscription_id: str,
) -> dict[str, object]:
    """Handle GET /subscriptions/{id} — retrieve subscription details.

    Args:
        subscription_id: The subscription to look up.

    Returns:
        Response dict with subscription details.
    """
    return {
        "status": "ok",
        "subscription_id": subscription_id,
    }


def cancel_subscription_endpoint(
    subscription_id: str, reason: str = "",
) -> dict[str, object]:
    """Handle POST /subscriptions/{id}/cancel — cancel a subscription.

    Args:
        subscription_id: The subscription to cancel.
        reason: Optional cancellation reason.

    Returns:
        Response dict confirming cancellation.
    """
    return {
        "status": "cancelled",
        "subscription_id": subscription_id,
        "reason": reason,
    }


def list_invoices_endpoint(
    customer_id: str, status_filter: str | None = None,
) -> dict[str, object]:
    """Handle GET /invoices — list invoices for a customer.

    Args:
        customer_id: The customer whose invoices to list.
        status_filter: Optional status to filter by.

    Returns:
        Response dict with invoice listing.
    """
    return {
        "status": "ok",
        "customer_id": customer_id,
        "status_filter": status_filter,
        "invoices": [],
    }


def register_webhook_endpoint(
    customer_id: str,
    endpoint_url: str,
    events: list[str] | None = None,
) -> dict[str, object]:
    """Handle POST /webhooks — register a webhook endpoint.

    Registers a URL to receive webhook events. If no specific
    events are listed, all events are subscribed.

    Args:
        customer_id: The customer registering the webhook.
        endpoint_url: The URL to deliver events to.
        events: List of event types to subscribe to.

    Returns:
        Registration confirmation with subscribed events.

    Raises:
        ValueError: If any requested event is not supported.
    """
    subscribed = events if events else list(WEBHOOK_EVENTS)

    invalid = [e for e in subscribed if e not in WEBHOOK_EVENTS]
    if invalid:
        raise ValueError(
            f"Unknown webhook events: {invalid}. "
            f"Supported: {WEBHOOK_EVENTS}"
        )

    return {
        "status": "registered",
        "customer_id": customer_id,
        "endpoint_url": endpoint_url,
        "subscribed_events": subscribed,
    }
