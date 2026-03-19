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

# Bulk discount tiers: minimum seats -> discount percentage
BULK_DISCOUNT_TIERS: dict[int, float] = {
    10: 0.10,   # 10+ seats: 10% discount
    50: 0.15,   # 50+ seats: 15% discount
    100: 0.20,  # 100+ seats: 20% discount
}

# Above this seat count, use custom pricing (no automatic discount)
CUSTOM_PRICING_THRESHOLD = 250

# Trial abuse prevention
MAX_TRIALS_PER_DOMAIN = 1
TRIAL_DOMAIN_WINDOW_DAYS = 90

# Disposable email domains that are blocked from trials
DISPOSABLE_EMAIL_DOMAINS = [
    "mailinator.com",
    "guerrillamail.com",
    "tempmail.com",
    "throwaway.email",
    "yopmail.com",
    "sharklasers.com",
    "guerrillamailblock.com",
    "grr.la",
    "dispostable.com",
    "maildrop.cc",
]

# Free tier trial requires a card on file
FREE_TRIAL_REQUIRES_CARD = True
