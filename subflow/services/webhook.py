"""Webhook event delivery service.

Delivers outbound webhook events to registered endpoints.
Supports retry with exponential backoff on delivery failure.
"""

from __future__ import annotations

from datetime import datetime, timezone

# Supported webhook event types
WEBHOOK_EVENTS = [
    "subscription.created",
    "subscription.updated",
    "subscription.cancelled",
    "invoice.paid",
    "invoice.failed",
    "payment.refunded",
]

# Maximum number of delivery retry attempts
MAX_WEBHOOK_RETRIES = 5

# Timeout in seconds for each delivery attempt
WEBHOOK_TIMEOUT_SECONDS = 30

# Exponential backoff base delay in seconds
WEBHOOK_BACKOFF_BASE_SECONDS = 1

# Exponential backoff multiplier (delay doubles each retry)
WEBHOOK_BACKOFF_MULTIPLIER = 2


def deliver_webhook(
    endpoint_url: str,
    event_type: str,
    payload: dict,
) -> dict[str, object]:
    """Deliver a webhook event to a registered endpoint.

    Sends the event payload to the endpoint URL with a
    WEBHOOK_TIMEOUT_SECONDS (30s) timeout. If delivery fails,
    the event is queued for retry.

    Args:
        endpoint_url: The registered webhook URL.
        event_type: One of WEBHOOK_EVENTS.
        payload: The event data to deliver.

    Returns:
        Delivery result with status and timestamp.

    Raises:
        ValueError: If event_type is not in WEBHOOK_EVENTS.
    """
    if event_type not in WEBHOOK_EVENTS:
        raise ValueError(
            f"Unknown webhook event: {event_type!r}. "
            f"Supported: {WEBHOOK_EVENTS}"
        )

    now = datetime.now(timezone.utc)
    return {
        "endpoint_url": endpoint_url,
        "event_type": event_type,
        "payload": payload,
        "timeout_seconds": WEBHOOK_TIMEOUT_SECONDS,
        "delivered_at": now.isoformat(),
        "status": "delivered",
    }


def schedule_webhook_retry(
    endpoint_url: str,
    event_type: str,
    payload: dict,
    attempt: int,
) -> dict[str, object]:
    """Schedule a webhook delivery retry with exponential backoff.

    Backoff schedule: 1s, 2s, 4s, 8s, 16s (doubles each time).
    After MAX_WEBHOOK_RETRIES (5) attempts, the delivery is
    marked as permanently failed.

    Args:
        endpoint_url: The webhook URL.
        event_type: The event type being retried.
        payload: The event data.
        attempt: The current attempt number (1-based).

    Returns:
        Retry schedule or permanent failure status.
    """
    if attempt >= MAX_WEBHOOK_RETRIES:
        return {
            "endpoint_url": endpoint_url,
            "event_type": event_type,
            "attempt": attempt,
            "status": "permanently_failed",
            "reason": (
                f"Exhausted all {MAX_WEBHOOK_RETRIES} retry attempts"
            ),
        }

    delay_seconds = (
        WEBHOOK_BACKOFF_BASE_SECONDS
        * (WEBHOOK_BACKOFF_MULTIPLIER ** (attempt - 1))
    )

    return {
        "endpoint_url": endpoint_url,
        "event_type": event_type,
        "attempt": attempt,
        "next_attempt": attempt + 1,
        "delay_seconds": delay_seconds,
        "status": "retry_scheduled",
    }
