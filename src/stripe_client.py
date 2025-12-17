"""
Stripe API Client - Wrapper for fetching payout-related data
"""

import os
from datetime import datetime
from typing import Optional, List, Dict, Any, Generator
import stripe
from dotenv import load_dotenv

# Load environment variables from .env.local first, then fall back to .env
load_dotenv('.env.local')
load_dotenv('.env')


class StripeClient:
    """Client for interacting with Stripe API to fetch payout data."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Stripe client.
        
        Args:
            api_key: Stripe API key. If not provided, uses STRIPE_API_KEY env var.
        """
        self.api_key = api_key or os.getenv('STRIPE_API_KEY')
        if not self.api_key:
            raise ValueError(
                "Stripe API key is required. Set STRIPE_API_KEY in .env.local "
                "or pass it directly."
            )
        stripe.api_key = self.api_key
    
    def get_payout(self, payout_id: str) -> stripe.Payout:
        """
        Fetch a single payout by ID.
        
        Args:
            payout_id: The Stripe payout ID (po_xxxxx)
            
        Returns:
            Stripe Payout object
        """
        return stripe.Payout.retrieve(payout_id)
    
    def list_payouts(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        status: str = "paid",
        limit: int = 100
    ) -> Generator[stripe.Payout, None, None]:
        """
        List payouts within a date range.
        
        Args:
            from_date: Start date (inclusive)
            to_date: End date (inclusive)
            status: Payout status filter (default: "paid")
            limit: Number of payouts per page
            
        Yields:
            Stripe Payout objects
        """
        params: Dict[str, Any] = {
            "status": status,
            "limit": limit
        }
        
        if from_date or to_date:
            params["created"] = {}
            if from_date:
                params["created"]["gte"] = int(from_date.timestamp())
            if to_date:
                params["created"]["lte"] = int(to_date.timestamp())
        
        payouts = stripe.Payout.list(**params)
        for payout in payouts.auto_paging_iter():
            yield payout
    
    def get_balance_transactions_for_payout(
        self,
        payout_id: str
    ) -> List[stripe.BalanceTransaction]:
        """
        Fetch all balance transactions associated with a payout.
        
        Args:
            payout_id: The Stripe payout ID
            
        Returns:
            List of BalanceTransaction objects
        """
        transactions = []
        params = {"payout": payout_id, "limit": 100}
        
        balance_transactions = stripe.BalanceTransaction.list(**params)
        for bt in balance_transactions.auto_paging_iter():
            transactions.append(bt)
        
        return transactions
    
    def get_charge(self, charge_id: str) -> Optional[stripe.Charge]:
        """
        Fetch a charge by ID.
        
        Args:
            charge_id: The Stripe charge ID (ch_xxxxx)
            
        Returns:
            Stripe Charge object or None if not found
        """
        try:
            return stripe.Charge.retrieve(
                charge_id,
                expand=["customer", "invoice", "balance_transaction"]
            )
        except stripe.error.InvalidRequestError:
            return None
    
    def get_refund(self, refund_id: str) -> Optional[stripe.Refund]:
        """
        Fetch a refund by ID.
        
        Args:
            refund_id: The Stripe refund ID (re_xxxxx)
            
        Returns:
            Stripe Refund object or None if not found
        """
        try:
            return stripe.Refund.retrieve(
                refund_id,
                expand=["charge", "balance_transaction"]
            )
        except stripe.error.InvalidRequestError:
            return None
    
    def get_invoice(self, invoice_id: str) -> Optional[stripe.Invoice]:
        """
        Fetch an invoice by ID.
        
        Args:
            invoice_id: The Stripe invoice ID (in_xxxxx)
            
        Returns:
            Stripe Invoice object or None if not found
        """
        try:
            return stripe.Invoice.retrieve(
                invoice_id,
                expand=["customer", "charge", "subscription"]
            )
        except stripe.error.InvalidRequestError:
            return None
    
    def get_dispute(self, dispute_id: str) -> Optional[stripe.Dispute]:
        """
        Fetch a dispute by ID.
        
        Args:
            dispute_id: The Stripe dispute ID (dp_xxxxx)
            
        Returns:
            Stripe Dispute object or None if not found
        """
        try:
            return stripe.Dispute.retrieve(dispute_id)
        except stripe.error.InvalidRequestError:
            return None
    
    def get_transfer(self, transfer_id: str) -> Optional[stripe.Transfer]:
        """
        Fetch a transfer by ID (for Connect accounts).
        
        Args:
            transfer_id: The Stripe transfer ID (tr_xxxxx)
            
        Returns:
            Stripe Transfer object or None if not found
        """
        try:
            return stripe.Transfer.retrieve(transfer_id)
        except stripe.error.InvalidRequestError:
            return None
    
    def get_payment_intent(self, payment_intent_id: str) -> Optional[stripe.PaymentIntent]:
        """
        Fetch a PaymentIntent by ID.
        
        Args:
            payment_intent_id: The Stripe PaymentIntent ID (pi_xxxxx)
            
        Returns:
            Stripe PaymentIntent object or None if not found
        """
        try:
            return stripe.PaymentIntent.retrieve(
                payment_intent_id,
                expand=["customer", "invoice", "charges"]
            )
        except stripe.error.InvalidRequestError:
            return None
    
    def get_payout_details(self, payout_id: str) -> Dict[str, Any]:
        """
        Fetch comprehensive payout details including all related transactions.
        
        Args:
            payout_id: The Stripe payout ID
            
        Returns:
            Dictionary containing payout and all related data
        """
        payout = self.get_payout(payout_id)
        balance_transactions = self.get_balance_transactions_for_payout(payout_id)
        
        # Collect related objects
        charges = []
        refunds = []
        invoices = []
        disputes = []
        transfers = []
        fees_breakdown = []
        
        # Track unique invoice IDs to avoid duplicates
        seen_invoices = set()
        
        for bt in balance_transactions:
            # Extract fee details
            if bt.fee_details:
                for fee in bt.fee_details:
                    fees_breakdown.append({
                        "transaction_id": bt.id,
                        "type": fee.type,
                        "amount": fee.amount,
                        "currency": fee.currency,
                        "description": fee.description
                    })
            
            # Get related object based on type
            source = bt.source
            if source:
                if source.startswith("ch_"):
                    charge = self.get_charge(source)
                    if charge:
                        charges.append(charge)
                        # Get associated invoice
                        if charge.invoice and charge.invoice not in seen_invoices:
                            invoice = self.get_invoice(charge.invoice)
                            if invoice:
                                invoices.append(invoice)
                                seen_invoices.add(charge.invoice)
                
                elif source.startswith("re_"):
                    refund = self.get_refund(source)
                    if refund:
                        refunds.append(refund)
                
                elif source.startswith("dp_"):
                    dispute = self.get_dispute(source)
                    if dispute:
                        disputes.append(dispute)
                
                elif source.startswith("tr_"):
                    transfer = self.get_transfer(source)
                    if transfer:
                        transfers.append(transfer)
                
                elif source.startswith("pi_"):
                    payment_intent = self.get_payment_intent(source)
                    if payment_intent:
                        # Extract charges from payment intent
                        if hasattr(payment_intent, 'charges') and payment_intent.charges:
                            for charge in payment_intent.charges.data:
                                charges.append(charge)
                                if charge.invoice and charge.invoice not in seen_invoices:
                                    invoice = self.get_invoice(charge.invoice)
                                    if invoice:
                                        invoices.append(invoice)
                                        seen_invoices.add(charge.invoice)
        
        return {
            "payout": payout,
            "balance_transactions": balance_transactions,
            "charges": charges,
            "refunds": refunds,
            "invoices": invoices,
            "disputes": disputes,
            "transfers": transfers,
            "fees_breakdown": fees_breakdown
        }

