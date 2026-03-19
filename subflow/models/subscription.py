"""Subscription and Plan domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Plan:
    """Represents a billing plan tier.

    Attributes:
        name: Tier identifier (free, pro, enterprise).
        monthly_price: Price in USD per month.
        max_seats: Maximum number of user seats.
        api_calls_per_month: Monthly API call quota.
        storage_gb: Storage allocation in gigabytes.
    """

    name: str
    monthly_price: int
    max_seats: int
    api_calls_per_month: int
    storage_gb: int

    def is_free(self) -> bool:
        """Return True if this plan has no monetary cost."""
        return self.monthly_price == 0

    def annual_price(self) -> int:
        """Calculate annual price with 2-month discount."""
        return self.monthly_price * 10  # 2 months free


@dataclass
class Subscription:
    """Tracks a customer's subscription lifecycle.

    Attributes:
        id: Unique subscription identifier.
        customer_id: Reference to the owning customer.
        plan: The associated billing plan.
        status: Current state (trial, active, paused, cancelled, expired).
        created_at: When the subscription was created.
        trial_end: When the trial period expires (if applicable).
        current_period_start: Start of current billing period.
        current_period_end: End of current billing period.
    """

    id: str
    customer_id: str
    plan: Plan
    status: str = "trial"
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    trial_end: datetime | None = None
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None

    def is_active(self) -> bool:
        """Return True if the subscription is in a usable state."""
        return self.status in ("trial", "active")
