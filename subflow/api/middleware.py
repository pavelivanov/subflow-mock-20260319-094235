"""API middleware for rate limiting and request validation.

Rate limits are enforced per customer based on their plan tier.
Limits are tracked per hour using a sliding window approach.
"""

from __future__ import annotations

# Rate limits per hour by plan tier
RATE_LIMITS_PER_HOUR: dict[str, int] = {
    "free": 100,
    "pro": 1000,
    "enterprise": 10000,
}


def check_rate_limit(
    customer_id: str,
    plan_tier: str,
    current_hour_requests: int,
) -> dict[str, object]:
    """Check whether a customer has exceeded their hourly rate limit.

    Args:
        customer_id: The customer making the request.
        plan_tier: Their current plan tier.
        current_hour_requests: Number of requests already made this hour.

    Returns:
        A dict with:
            - allowed: bool — whether the request should proceed.
            - limit: int — the hourly limit for this tier.
            - remaining: int — requests remaining this hour.
            - retry_after_seconds: int — seconds until limit resets
              (only present when rate limited).
    """
    limit = RATE_LIMITS_PER_HOUR.get(plan_tier, RATE_LIMITS_PER_HOUR["free"])
    remaining = max(0, limit - current_hour_requests)

    if current_hour_requests >= limit:
        return {
            "allowed": False,
            "limit": limit,
            "remaining": 0,
            "customer_id": customer_id,
            "retry_after_seconds": 3600,
        }

    return {
        "allowed": True,
        "limit": limit,
        "remaining": remaining,
        "customer_id": customer_id,
    }
