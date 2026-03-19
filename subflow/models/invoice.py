"""Invoice and LineItem domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class LineItem:
    """A single line item on an invoice.

    Attributes:
        description: Human-readable description of the charge.
        quantity: Number of units.
        unit_price: Price per unit in USD.
        total: Computed total (quantity * unit_price).
    """

    description: str
    quantity: int
    unit_price: float
    total: float = 0.0

    def __post_init__(self) -> None:
        """Compute total from quantity and unit price."""
        if self.total == 0.0:
            self.total = self.quantity * self.unit_price


@dataclass
class Invoice:
    """Represents a billing invoice for a customer.

    Attributes:
        id: Unique invoice identifier.
        subscription_id: The subscription this invoice belongs to.
        customer_id: The billed customer.
        status: Invoice state (draft, issued, paid, overdue, void).
        line_items: Individual charges on the invoice.
        issued_at: When the invoice was issued.
        due_at: Payment due date.
        paid_at: When payment was received (if applicable).
        total_amount: Sum of all line item totals.
    """

    id: str
    subscription_id: str
    customer_id: str
    status: str = "draft"
    line_items: list[LineItem] = field(default_factory=list)
    issued_at: datetime | None = None
    due_at: datetime | None = None
    paid_at: datetime | None = None
    total_amount: float = 0.0

    def calculate_total(self) -> float:
        """Recalculate the total from line items."""
        self.total_amount = sum(item.total for item in self.line_items)
        return self.total_amount

    def is_overdue(self) -> bool:
        """Check whether this invoice is past its due date."""
        if self.status == "paid" or self.due_at is None:
            return False
        return datetime.now(timezone.utc) > self.due_at
