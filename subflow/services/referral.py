"""Referral program service.

Manages customer referral credits, validation, and tracking.
Referrers earn a percentage credit on referred subscriptions,
and referred customers get free months.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

# Referrer gets this percentage of the referred subscription price
REFERRAL_CREDIT_PERCENT = 20

# Maximum credit per single referral (USD)
MAX_REFERRAL_CREDIT = 50.00

# Maximum total referral credits per year (USD)
MAX_ANNUAL_REFERRAL_CREDIT = 500.00

# Referral links expire after this many days
REFERRAL_VALIDITY_DAYS = 90

# Referred customer gets this many months free
REFEREE_FREE_MONTHS = 1
