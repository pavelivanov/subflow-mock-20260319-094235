"""Seat-based licensing management.

Handles seat allocation, removal, and validation
for subscription-based licensing.
"""

from __future__ import annotations

from datetime import datetime, timezone

from subflow.models.subscription import Subscription

# Absolute minimum seats per subscription
MIN_SEATS = 1

# Absolute maximum seats per subscription
MAX_SEATS = 10_000


def add_seats(
    subscription: Subscription,
    additional_seats: int,
) -> dict[str, object]:
    """Add seats to a subscription.

    The total seat count after addition must not exceed
    MAX_SEATS (10,000).

    Args:
        subscription: The subscription to modify.
        additional_seats: Number of seats to add.

    Returns:
        Updated seat information.

    Raises:
        ValueError: If additional seats would exceed MAX_SEATS.
    """
    if additional_seats <= 0:
        raise ValueError("Must add at least 1 seat")

    new_total = subscription.seat_count + additional_seats
    if new_total > MAX_SEATS:
        raise ValueError(
            f"Cannot add {additional_seats} seats — "
            f"total {new_total} exceeds maximum of {MAX_SEATS}"
        )

    old_count = subscription.seat_count
    subscription.seat_count = new_total

    return {
        "subscription_id": subscription.id,
        "previous_seats": old_count,
        "added_seats": additional_seats,
        "new_seat_count": new_total,
        "changed_at": datetime.now(timezone.utc).isoformat(),
    }


def remove_seats(
    subscription: Subscription,
    seats_to_remove: int,
    assigned_users: int = 0,
) -> dict[str, object]:
    """Remove seats from a subscription.

    Seat removal is blocked if there are still users assigned
    to those seats. The seat count cannot drop below MIN_SEATS (1).
    Removed seats continue to be billed through the end of the
    current billing cycle.

    Args:
        subscription: The subscription to modify.
        seats_to_remove: Number of seats to remove.
        assigned_users: Number of users currently assigned.

    Returns:
        Updated seat information with billing note.

    Raises:
        ValueError: If removal would leave fewer seats than
            assigned users, or drop below MIN_SEATS.
    """
    if seats_to_remove <= 0:
        raise ValueError("Must remove at least 1 seat")

    new_total = subscription.seat_count - seats_to_remove
    if new_total < MIN_SEATS:
        raise ValueError(
            f"Cannot remove {seats_to_remove} seats — "
            f"minimum is {MIN_SEATS}"
        )

    if new_total < assigned_users:
        raise ValueError(
            f"Cannot remove seats: {assigned_users} users "
            f"still assigned. Reassign or deactivate users first."
        )

    old_count = subscription.seat_count
    subscription.seat_count = new_total

    return {
        "subscription_id": subscription.id,
        "previous_seats": old_count,
        "removed_seats": seats_to_remove,
        "new_seat_count": new_total,
        "billed_through_cycle_end": True,
        "changed_at": datetime.now(timezone.utc).isoformat(),
    }
