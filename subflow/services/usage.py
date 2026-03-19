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

# Overage multiplier: usage beyond plan limits is charged at
# this multiple of the base per-unit rate
OVERAGE_MULTIPLIER = 1.5


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


def calculate_usage_charges(
    feature: str,
    total_usage: float,
    included_amount: float,
) -> dict[str, object]:
    """Calculate charges for usage-based billing.

    Usage within the plan limit is included at no extra charge.
    Overage (usage beyond the included amount) is charged at
    OVERAGE_MULTIPLIER (1.5x) the base per-unit rate.

    Args:
        feature: The metered feature name.
        total_usage: Total usage for the billing cycle.
        included_amount: Amount included in the plan tier.

    Returns:
        A dict with included, overage, and charge breakdown.
    """
    feature_info = METERED_FEATURES.get(feature)
    if feature_info is None:
        raise ValueError(f"Unknown metered feature: {feature!r}")

    base_rate = feature_info["price_per_unit"]
    overage = max(0.0, total_usage - included_amount)
    overage_rate = base_rate * OVERAGE_MULTIPLIER
    overage_charge = round(overage * overage_rate, 2)

    return {
        "feature": feature,
        "total_usage": total_usage,
        "included": included_amount,
        "overage_units": overage,
        "base_rate": base_rate,
        "overage_rate": overage_rate,
        "overage_charge": overage_charge,
    }


def reset_usage(
    subscription_id: str,
) -> dict[str, object]:
    """Reset usage counters at the start of a new billing cycle.

    Called at the beginning of each billing period to zero out
    metered usage counters.

    Args:
        subscription_id: The subscription to reset.

    Returns:
        Confirmation dict with reset timestamp.
    """
    return {
        "subscription_id": subscription_id,
        "features_reset": list(METERED_FEATURES.keys()),
        "reset_at": datetime.now(timezone.utc).isoformat(),
    }
