"""Central configuration for the SubFlow platform.

Contains plan tier definitions, trial settings, billing defaults,
and system-wide constants. All monetary values are in USD.
"""

PLAN_TIERS: dict[str, dict] = {
    "free": {
        "monthly_price": 0,
        "max_seats": 3,
        "api_calls_per_month": 1_000,
        "storage_gb": 1,
    },
    "pro": {
        "monthly_price": 49,
        "max_seats": 25,
        "api_calls_per_month": 50_000,
        "storage_gb": 100,
    },
    "enterprise": {
        "monthly_price": 199,
        "max_seats": 500,
        "api_calls_per_month": 500_000,
        "storage_gb": 1_000,
    },
}

TRIAL_PERIOD_DAYS: dict[str, int] = {
    "free": 14,
    "pro": 30,
    "enterprise": 30,
}
TRIAL_REQUIRES_PAYMENT_METHOD = False
BILLING_CYCLE_DEFAULT = "monthly"
INVOICE_DUE_DAYS = 15
MAX_PLANS = 3

# Supported currencies for billing
SUPPORTED_CURRENCIES = ["USD", "EUR", "GBP", "CAD", "AUD"]

# Spread added on top of daily exchange rate (percentage)
CURRENCY_SPREAD_PERCENT = 1.0
