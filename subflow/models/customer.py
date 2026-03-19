"""Customer and PaymentMethod domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class PaymentMethod:
    """A stored payment method for a customer.

    Attributes:
        id: Unique identifier for this payment method.
        method_type: One of card, ach, wire.
        last_four: Last four digits/characters of the account.
        is_default: Whether this is the default payment method.
        expires_at: Expiry date for cards, None for other types.
    """

    id: str
    method_type: str  # card, ach, wire
    last_four: str
    is_default: bool = False
    expires_at: datetime | None = None

    def is_expired(self) -> bool:
        """Check whether this payment method has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at


@dataclass
class Customer:
    """Represents a SubFlow customer account.

    Attributes:
        id: Unique customer identifier.
        email: Primary contact email.
        company_name: Organization name.
        created_at: Account creation timestamp.
        payment_methods: Stored payment methods.
    """

    id: str
    email: str
    company_name: str
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    payment_methods: list[PaymentMethod] = field(
        default_factory=list,
    )

    def default_payment_method(self) -> PaymentMethod | None:
        """Return the default payment method, or None."""
        for pm in self.payment_methods:
            if pm.is_default and not pm.is_expired():
                return pm
        return None

    def has_valid_payment_method(self) -> bool:
        """Check whether at least one non-expired method exists."""
        return any(
            not pm.is_expired() for pm in self.payment_methods
        )
