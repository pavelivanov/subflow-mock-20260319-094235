"""Usage-based billing service.

Tracks metered feature usage (API calls, storage, team seats)
and calculates usage-based charges for billing.
"""

from __future__ import annotations

from datetime import datetime, timezone

# Metered features and their per-unit pricing
METERED_FEATURES: dict[str, dict] = {
    "api_calls": {
        "unit": "per 1000 calls",
        "price_per_unit": 0.50,
    },
    "storage_gb": {
        "unit": "per GB",
        "price_per_unit": 0.10,
    },
    "team_seats": {
        "unit": "per seat",
        "price_per_unit": 10.00,
    },
}


def track_usage(
    subscription_id: str,
    feature: str,
    quantity: float,
) -> dict[str, object]:
    """Record usage of a metered feature.

    Args:
        subscription_id: The subscription using the feature.
        feature: Feature name (api_calls, storage_gb, team_seats).
        quantity: Amount consumed.

    Returns:
        Usage record with timestamp.

    Raises:
        ValueError: If the feature is not in METERED_FEATURES.
    """
    if feature not in METERED_FEATURES:
        raise ValueError(
            f"Unknown metered feature: {feature!r}. "
            f"Available: {list(METERED_FEATURES.keys())}"
        )
    return {
        "subscription_id": subscription_id,
        "feature": feature,
        "quantity": quantity,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }


def get_current_usage(
    subscription_id: str,
    feature: str,
    usage_records: list[dict],
) -> float:
    """Get total usage for a feature in the current billing cycle.

    Args:
        subscription_id: The subscription to check.
        feature: The metered feature name.
        usage_records: List of usage records to aggregate.

    Returns:
        Total usage quantity for the feature.
    """
    total = 0.0
    for record in usage_records:
        if (
            record["subscription_id"] == subscription_id
            and record["feature"] == feature
        ):
            total += record["quantity"]
    return total
