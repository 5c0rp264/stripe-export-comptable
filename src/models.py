"""
Data models for Stripe payout export
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from decimal import Decimal


@dataclass
class TransactionRecord:
    """Represents a single financial transaction for accounting purposes."""
    
    date: datetime
    reference: str  # Stripe transaction ID (txn_xxx)
    type: str  # Transaction type (Paiement, Remboursement, Frais, etc.)
    description: str
    montant_brut: Decimal  # Gross amount in cents
    frais: Decimal  # Fees in cents
    montant_net: Decimal  # Net amount in cents
    devise: str  # Currency (EUR, USD, etc.)
    client: Optional[str] = None  # Customer name/email
    numero_facture: Optional[str] = None  # Invoice number
    source_id: Optional[str] = None  # Source object ID (ch_, pi_, re_, etc.) for dashboard links
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for export."""
        return {
            "Date": self.date,
            "Référence": self.reference,
            "Type": self.type,
            "Description": self.description,
            "Montant Brut": self.montant_brut,
            "Frais": self.frais,
            "Montant Net": self.montant_net,
            "Devise": self.devise,
            "Client": self.client or "",
            "N° Facture": self.numero_facture or ""
        }


@dataclass
class InvoiceRecord:
    """Represents an invoice for accounting purposes."""
    
    numero: str  # Invoice number
    date: datetime
    date_echeance: Optional[datetime]  # Due date
    client_nom: str
    client_email: str
    montant_ht: Decimal  # Amount excluding tax
    montant_tva: Decimal  # VAT amount
    montant_ttc: Decimal  # Total amount including tax
    devise: str
    statut: str  # paid, open, void, etc.
    pdf_url: Optional[str] = None
    stripe_id: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for export."""
        return {
            "N° Facture": self.numero,
            "Date": self.date,
            "Date Échéance": self.date_echeance,
            "Client": self.client_nom,
            "Email": self.client_email,
            "Montant HT": self.montant_ht,
            "TVA": self.montant_tva,
            "Montant TTC": self.montant_ttc,
            "Devise": self.devise,
            "Statut": self.statut,
            "ID Stripe": self.stripe_id
        }


@dataclass
class FeeRecord:
    """Represents a fee breakdown for accounting purposes."""
    
    transaction_id: str
    type: str  # stripe_fee, application_fee, etc.
    description: str
    montant: Decimal
    devise: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for export."""
        return {
            "Transaction": self.transaction_id,
            "Type": self.type,
            "Description": self.description,
            "Montant": self.montant,
            "Devise": self.devise
        }


@dataclass
class RefundRecord:
    """Represents a refund for accounting purposes."""
    
    refund_id: str
    date: datetime
    montant: Decimal
    devise: str
    statut: str
    raison: Optional[str] = None
    charge_id: Optional[str] = None
    invoice_number: Optional[str] = None
    client_nom: Optional[str] = None
    credit_note_number: Optional[str] = None
    credit_note_pdf_url: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for export."""
        return {
            "ID Remboursement": self.refund_id,
            "Date": self.date,
            "Montant": self.montant,
            "Devise": self.devise,
            "Statut": self.statut,
            "Raison": self.raison or "",
            "ID Charge": self.charge_id or "",
            "N° Facture": self.invoice_number or "",
            "Client": self.client_nom or "",
            "N° Avoir": self.credit_note_number or "",
        }


@dataclass 
class CreditNoteRecord:
    """Represents a credit note (avoir) for accounting purposes."""
    
    numero: str  # Credit note number
    date: datetime
    invoice_number: Optional[str]
    client_nom: str
    client_email: str
    montant: Decimal  # Total amount
    devise: str
    statut: str  # issued, void
    raison: Optional[str] = None
    pdf_url: Optional[str] = None
    stripe_id: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for export."""
        return {
            "N° Avoir": self.numero,
            "Date": self.date,
            "N° Facture Origine": self.invoice_number or "",
            "Client": self.client_nom,
            "Email": self.client_email,
            "Montant": self.montant,
            "Devise": self.devise,
            "Statut": self.statut,
            "Raison": self.raison or "",
            "ID Stripe": self.stripe_id
        }


@dataclass
class PayoutSummary:
    """Summary of a payout for the accounting report."""
    
    payout_id: str
    date: datetime
    date_arrivee: datetime  # Arrival date
    montant: Decimal
    devise: str
    statut: str
    methode: str  # standard, instant
    banque: str  # Bank account info
    
    # Aggregated amounts
    total_paiements: Decimal = Decimal(0)
    total_remboursements: Decimal = Decimal(0)
    total_frais: Decimal = Decimal(0)
    total_litiges: Decimal = Decimal(0)
    total_autres: Decimal = Decimal(0)
    
    # Counts
    nb_transactions: int = 0
    nb_factures: int = 0
    nb_remboursements: int = 0
    nb_litiges: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for export."""
        return {
            "ID Payout": self.payout_id,
            "Date": self.date,
            "Date Arrivée": self.date_arrivee,
            "Montant": self.montant,
            "Devise": self.devise,
            "Statut": self.statut,
            "Méthode": self.methode,
            "Banque": self.banque,
            "Total Paiements": self.total_paiements,
            "Total Remboursements": self.total_remboursements,
            "Total Frais Stripe": self.total_frais,
            "Total Litiges": self.total_litiges,
            "Total Autres": self.total_autres,
            "Nb Transactions": self.nb_transactions,
            "Nb Factures": self.nb_factures,
            "Nb Remboursements": self.nb_remboursements,
            "Nb Litiges": self.nb_litiges
        }


@dataclass
class PayoutExportData:
    """Complete export data for a payout."""
    
    summary: PayoutSummary
    transactions: List[TransactionRecord]
    invoices: List[InvoiceRecord]
    fees: List[FeeRecord]
    refunds: List[RefundRecord] = field(default_factory=list)
    credit_notes: List[CreditNoteRecord] = field(default_factory=list)
    raw_data: Dict[str, Any] = field(default_factory=dict)
    account_id: Optional[str] = None  # Stripe account ID for dashboard URLs

