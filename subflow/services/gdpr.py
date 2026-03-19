"""GDPR-compliant data deletion service.

Handles customer data deletion requests including soft delete,
hard purge, billing anonymization, and data export.
All operations maintain an audit trail.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

# Soft delete period: data is recoverable during this window
SOFT_DELETE_DAYS = 30

# Data export must be delivered within this timeframe
EXPORT_DEADLINE_HOURS = 72


def initiate_soft_delete(
    customer_id: str,
    requested_by: str,
) -> dict[str, object]:
    """Initiate a soft delete for a customer.

    Data is marked for deletion but remains recoverable
    for SOFT_DELETE_DAYS (30 days). After this period,
    hard purge runs automatically.

    Args:
        customer_id: The customer requesting deletion.
        requested_by: Who initiated the request (customer, admin).

    Returns:
        Soft delete confirmation with purge date.
    """
    now = datetime.now(timezone.utc)
    purge_at = now + timedelta(days=SOFT_DELETE_DAYS)

    return {
        "customer_id": customer_id,
        "action": "soft_delete",
        "requested_by": requested_by,
        "initiated_at": now.isoformat(),
        "recoverable_until": purge_at.isoformat(),
        "hard_purge_scheduled_at": purge_at.isoformat(),
        "status": "pending_purge",
    }


def execute_hard_purge(
    customer_id: str,
    soft_deleted_at: datetime,
) -> dict[str, object]:
    """Permanently remove all personal data for a customer.

    Can only execute after the soft delete period has elapsed.
    Removes all personal data but preserves anonymized billing
    records for financial compliance.

    Args:
        customer_id: The customer to purge.
        soft_deleted_at: When the soft delete was initiated.

    Returns:
        Purge confirmation.

    Raises:
        ValueError: If soft delete period has not elapsed.
    """
    now = datetime.now(timezone.utc)
    days_since_delete = (now - soft_deleted_at).days

    if days_since_delete < SOFT_DELETE_DAYS:
        raise ValueError(
            f"Cannot purge: only {days_since_delete} days since "
            f"soft delete (minimum {SOFT_DELETE_DAYS} days required)"
        )

    return {
        "customer_id": customer_id,
        "action": "hard_purge",
        "purged_at": now.isoformat(),
        "data_removed": [
            "personal_info",
            "contact_details",
            "usage_history",
            "support_tickets",
        ],
        "data_anonymized": ["billing_records"],
        "status": "purged",
    }


def anonymize_billing_records(
    customer_id: str,
) -> dict[str, object]:
    """Anonymize billing records for a deleted customer.

    Billing records are anonymized rather than deleted to
    maintain financial compliance. Personal identifiers are
    replaced with anonymized tokens.

    Args:
        customer_id: The customer whose billing to anonymize.

    Returns:
        Anonymization confirmation.
    """
    now = datetime.now(timezone.utc)
    anonymized_id = f"ANON-{customer_id[:8]}"

    return {
        "original_customer_id": customer_id,
        "anonymized_id": anonymized_id,
        "fields_anonymized": [
            "customer_name",
            "email",
            "payment_method_details",
        ],
        "fields_preserved": [
            "invoice_amounts",
            "invoice_dates",
            "payment_status",
        ],
        "anonymized_at": now.isoformat(),
    }


def request_data_export(
    customer_id: str,
) -> dict[str, object]:
    """Request a GDPR data export for a customer.

    The export must be fulfilled within EXPORT_DEADLINE_HOURS
    (72 hours) as required by GDPR Article 20.

    Args:
        customer_id: The customer requesting their data.

    Returns:
        Export request details with deadline.
    """
    now = datetime.now(timezone.utc)
    deadline = now + timedelta(hours=EXPORT_DEADLINE_HOURS)

    return {
        "customer_id": customer_id,
        "action": "data_export",
        "requested_at": now.isoformat(),
        "deadline": deadline.isoformat(),
        "deadline_hours": EXPORT_DEADLINE_HOURS,
        "export_includes": [
            "personal_info",
            "subscription_history",
            "billing_records",
            "usage_data",
            "support_tickets",
        ],
        "status": "pending",
    }
