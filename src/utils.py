"""
Utility functions for Stripe comptable export
"""

import os
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional, List
import locale


# Transaction type translations
TRANSACTION_TYPES = {
    "charge": "Paiement",
    "payment": "Paiement",
    "refund": "Remboursement",
    "adjustment": "Ajustement",
    "application_fee": "Commission Application",
    "application_fee_refund": "Remb. Commission",
    "transfer": "Transfert",
    "payout": "Virement",
    "payout_failure": "Échec Virement",
    "stripe_fee": "Frais Stripe",
    "network_cost": "Coûts Réseau",
    "dispute": "Litige",
    "dispute_won": "Litige Gagné",
    "dispute_lost": "Litige Perdu",
    "issuing_authorization_hold": "Autorisation",
    "issuing_authorization_release": "Libération Autorisation",
    "issuing_dispute": "Litige Issuing",
    "issuing_transaction": "Transaction Issuing",
}

# Invoice status translations
INVOICE_STATUS = {
    "draft": "Brouillon",
    "open": "Ouverte",
    "paid": "Payée",
    "uncollectible": "Irrécouvrable",
    "void": "Annulée",
}

# Payout status translations
PAYOUT_STATUS = {
    "paid": "Payé",
    "pending": "En attente",
    "in_transit": "En transit",
    "canceled": "Annulé",
    "failed": "Échoué",
}

# Fee type translations
FEE_TYPES = {
    "stripe_fee": "Frais Stripe",
    "application_fee": "Commission Application",
    "network_cost": "Coûts Réseau",
    "tax": "Taxe",
}

# Refund reason translations
REFUND_REASONS = {
    "duplicate": "Doublon",
    "fraudulent": "Fraude",
    "requested_by_customer": "Demande client",
    "expired_uncaptured_charge": "Charge expirée",
}

# Credit note status translations
CREDIT_NOTE_STATUS = {
    "issued": "Émis",
    "void": "Annulé",
}

# Refund status translations
REFUND_STATUS = {
    "pending": "En attente",
    "succeeded": "Effectué",
    "failed": "Échoué",
    "canceled": "Annulé",
    "requires_action": "Action requise",
}


def format_currency_fr(
    amount_cents: int,
    currency: str,
    include_symbol: bool = True
) -> str:
    """
    Format a currency amount in French format.
    
    Args:
        amount_cents: Amount in cents/centimes
        currency: ISO currency code (EUR, USD, etc.)
        include_symbol: Whether to include the currency symbol
        
    Returns:
        Formatted string like "1 234,56 €" or "1 234,56"
    """
    amount = Decimal(amount_cents) / 100
    
    # Format with French locale (space as thousands separator, comma as decimal)
    formatted = f"{amount:,.2f}".replace(",", " ").replace(".", ",")
    
    if include_symbol:
        symbol = get_currency_symbol(currency)
        return f"{formatted} {symbol}"
    return formatted


def get_currency_symbol(currency: str) -> str:
    """Get the currency symbol for a currency code."""
    symbols = {
        "EUR": "€",
        "USD": "$",
        "GBP": "£",
        "CHF": "CHF",
        "CAD": "$ CA",
        "AUD": "$ AU",
        "JPY": "¥",
    }
    return symbols.get(currency.upper(), currency.upper())


def cents_to_decimal(amount_cents: int) -> Decimal:
    """Convert amount in cents to Decimal."""
    return Decimal(amount_cents) / 100


def format_date_fr(dt: datetime, include_time: bool = False) -> str:
    """
    Format a datetime in French format.
    
    Args:
        dt: Datetime object
        include_time: Whether to include time
        
    Returns:
        Formatted string like "17/12/2024" or "17/12/2024 14:30"
    """
    if include_time:
        return dt.strftime("%d/%m/%Y %H:%M")
    return dt.strftime("%d/%m/%Y")


def timestamp_to_datetime(timestamp: int) -> datetime:
    """Convert Unix timestamp to datetime."""
    return datetime.fromtimestamp(timestamp)


def translate_transaction_type(stripe_type: str) -> str:
    """Translate Stripe transaction type to French."""
    return TRANSACTION_TYPES.get(stripe_type, stripe_type.replace("_", " ").title())


def translate_invoice_status(status: str) -> str:
    """Translate invoice status to French."""
    return INVOICE_STATUS.get(status, status.title())


def translate_payout_status(status: str) -> str:
    """Translate payout status to French."""
    return PAYOUT_STATUS.get(status, status.title())


def translate_fee_type(fee_type: str) -> str:
    """Translate fee type to French."""
    return FEE_TYPES.get(fee_type, fee_type.replace("_", " ").title())


def translate_refund_reason(reason: Optional[str]) -> str:
    """Translate refund reason to French."""
    if not reason:
        return ""
    return REFUND_REASONS.get(reason, reason.replace("_", " ").title())


def translate_refund_status(status: str) -> str:
    """Translate refund status to French."""
    return REFUND_STATUS.get(status, status.title())


def translate_credit_note_status(status: str) -> str:
    """Translate credit note status to French."""
    return CREDIT_NOTE_STATUS.get(status, status.title())


def get_customer_display_name(customer: Any) -> str:
    """
    Get a display name for a Stripe customer.
    
    Args:
        customer: Stripe Customer object or dict
        
    Returns:
        Customer name, email, or ID
    """
    if not customer:
        return ""
    
    if isinstance(customer, str):
        return customer
    
    # Try to get name first, then email, then ID
    if hasattr(customer, 'name') and customer.name:
        return customer.name
    if hasattr(customer, 'email') and customer.email:
        return customer.email
    if hasattr(customer, 'id'):
        return customer.id
    
    return str(customer)


def safe_get(obj: Any, *keys: str, default: Any = None) -> Any:
    """
    Safely get nested attributes or dictionary keys.
    
    Args:
        obj: Object or dictionary to access
        keys: Sequence of keys/attributes to traverse
        default: Default value if not found
        
    Returns:
        Value at the path or default
    """
    current = obj
    for key in keys:
        if current is None:
            return default
        if isinstance(current, dict):
            current = current.get(key)
        elif hasattr(current, key):
            current = getattr(current, key, None)
        else:
            return default
    return current if current is not None else default


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a string for use as a filename.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename safe for filesystem
    """
    # Replace problematic characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # Remove leading/trailing spaces and dots
    filename = filename.strip(' .')
    
    # Limit length
    if len(filename) > 200:
        filename = filename[:200]
    
    return filename


def ensure_dir(path: str) -> str:
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        path: Directory path
        
    Returns:
        The path
    """
    os.makedirs(path, exist_ok=True)
    return path


def get_bank_account_display(bank_account: Any) -> str:
    """
    Get a display string for a bank account.
    
    Args:
        bank_account: Stripe BankAccount object
        
    Returns:
        Display string like "FR76 **** 1234 (BNP Paribas)"
    """
    if not bank_account:
        return ""
    
    parts = []
    
    country = safe_get(bank_account, 'country', default='')
    last4 = safe_get(bank_account, 'last4', default='')
    bank_name = safe_get(bank_account, 'bank_name', default='')
    
    if country:
        parts.append(country)
    if last4:
        parts.append(f"**** {last4}")
    if bank_name:
        parts.append(f"({bank_name})")
    
    return " ".join(parts)


def get_stripe_dashboard_url(stripe_id: str, account_id: Optional[str] = None) -> Optional[str]:
    """
    Get the Stripe dashboard URL for a given Stripe object ID.
    
    Args:
        stripe_id: A Stripe object ID (e.g., ch_xxx, po_xxx, re_xxx)
        account_id: The Stripe account ID (acct_xxx) for building full URLs
        
    Returns:
        Dashboard URL or None if the ID format is not recognized or not linkable
    """
    if not stripe_id:
        return None
    
    # Mapping of Stripe ID prefixes to dashboard paths
    # Only include objects that have actual dashboard pages
    url_mappings = {
        "ch_": "payments",           # Charges
        "pi_": "payments",           # Payment Intents
        "py_": "payments",           # Legacy payments
        "re_": "refunds",            # Refunds
        "po_": "payouts",            # Payouts
        "dp_": "disputes",           # Disputes
        "in_": "invoices",           # Invoices
        "cus_": "customers",         # Customers
        "sub_": "subscriptions",     # Subscriptions
        "tr_": "connect/transfers",  # Transfers
    }
    
    # Balance transactions (txn_) don't have their own dashboard page
    # Use the source object instead
    if stripe_id.startswith("txn_"):
        return None
    
    base_url = "https://dashboard.stripe.com"
    
    for prefix, path in url_mappings.items():
        if stripe_id.startswith(prefix):
            if account_id:
                return f"{base_url}/{account_id}/{path}/{stripe_id}"
            else:
                return f"{base_url}/{path}/{stripe_id}"
    
    # For unknown prefixes, return None
    return None

