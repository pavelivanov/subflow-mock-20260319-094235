"""Tax calculation service.

Handles US state sales tax (nexus-based), EU VAT
(reverse charge for B2B, standard rates for B2C),
and tax exemption certificate validation.
"""

from __future__ import annotations

from datetime import datetime, timezone

# US states where SubFlow has established nexus
US_NEXUS_STATES = ["CA", "NY", "TX", "WA", "IL"]

# US state sales tax rates (percentage)
US_STATE_TAX_RATES: dict[str, float] = {
    "CA": 7.25,
    "NY": 8.0,
    "TX": 6.25,
    "WA": 6.5,
    "IL": 6.25,
}

# EU VAT rates by country code (percentage)
EU_VAT_RATES: dict[str, float] = {
    "DE": 19.0,
    "FR": 20.0,
    "NL": 21.0,
    "IT": 22.0,
    "ES": 21.0,
    "SE": 25.0,
    "IE": 23.0,
    "PL": 23.0,
    "BE": 21.0,
    "AT": 20.0,
}


def calculate_tax(
    amount: float,
    country: str,
    state: str | None = None,
    is_b2b: bool = False,
    tax_exempt: bool = False,
) -> dict[str, object]:
    """Calculate applicable tax for an invoice amount.

    Tax rules:
        - US: Sales tax only in nexus states (CA, NY, TX, WA, IL).
        - EU B2B: Reverse charge applies (0%% VAT).
        - EU B2C: Destination country VAT rate.
        - Tax-exempt customers: No tax collected.

    Args:
        amount: Pre-tax invoice amount in USD.
        country: Two-letter country code (US, DE, FR, etc.).
        state: US state code (required for US addresses).
        is_b2b: Whether the customer is a business.
        tax_exempt: Whether the customer has a valid exemption.

    Returns:
        Tax calculation details including rate, amount, and type.
    """
    if tax_exempt:
        return {
            "taxable_amount": amount,
            "tax_rate": 0.0,
            "tax_amount": 0.0,
            "tax_type": "exempt",
            "country": country,
        }

    # US sales tax — only in nexus states
    if country == "US":
        if state and state in US_NEXUS_STATES:
            rate = US_STATE_TAX_RATES.get(state, 0.0)
            tax_amount = round(amount * (rate / 100), 2)
            return {
                "taxable_amount": amount,
                "tax_rate": rate,
                "tax_amount": tax_amount,
                "tax_type": "us_sales_tax",
                "country": country,
                "state": state,
            }
        return {
            "taxable_amount": amount,
            "tax_rate": 0.0,
            "tax_amount": 0.0,
            "tax_type": "us_no_nexus",
            "country": country,
            "state": state,
        }

    # EU VAT
    if country in EU_VAT_RATES:
        if is_b2b:
            return apply_reverse_charge(amount, country)
        rate = EU_VAT_RATES[country]
        tax_amount = round(amount * (rate / 100), 2)
        return {
            "taxable_amount": amount,
            "tax_rate": rate,
            "tax_amount": tax_amount,
            "tax_type": "eu_vat",
            "country": country,
        }

    # Other countries — no tax collected
    return {
        "taxable_amount": amount,
        "tax_rate": 0.0,
        "tax_amount": 0.0,
        "tax_type": "not_applicable",
        "country": country,
    }


def check_tax_exemption(
    customer_id: str,
    certificate_id: str | None = None,
    certificate_expiry: datetime | None = None,
) -> dict[str, object]:
    """Check whether a customer has a valid tax exemption.

    Requires both a certificate ID and a non-expired certificate.

    Args:
        customer_id: The customer to check.
        certificate_id: The exemption certificate identifier.
        certificate_expiry: When the certificate expires.

    Returns:
        Exemption status details.
    """
    if certificate_id is None:
        return {
            "customer_id": customer_id,
            "exempt": False,
            "reason": "No certificate on file",
        }

    now = datetime.now(timezone.utc)
    if certificate_expiry is not None and certificate_expiry < now:
        return {
            "customer_id": customer_id,
            "exempt": False,
            "reason": "Certificate expired",
            "certificate_id": certificate_id,
            "expired_at": certificate_expiry.isoformat(),
        }

    return {
        "customer_id": customer_id,
        "exempt": True,
        "certificate_id": certificate_id,
        "valid_until": (
            certificate_expiry.isoformat()
            if certificate_expiry else None
        ),
    }


def apply_reverse_charge(
    amount: float,
    country: str,
) -> dict[str, object]:
    """Apply EU reverse charge for B2B transactions.

    Under the reverse charge mechanism, the supplier does not
    charge VAT. The business customer self-accounts for VAT
    in their own country.

    Args:
        amount: Invoice amount before tax.
        country: EU country code.

    Returns:
        Reverse charge details with 0%% VAT.
    """
    return {
        "taxable_amount": amount,
        "tax_rate": 0.0,
        "tax_amount": 0.0,
        "tax_type": "eu_reverse_charge",
        "country": country,
        "local_vat_rate": EU_VAT_RATES.get(country, 0.0),
        "note": "Reverse charge — customer to self-account for VAT",
    }
