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
        self._account_id: Optional[str] = None
    
    def get_account_id(self) -> str:
        """
        Get the Stripe account ID for building dashboard URLs.
        
        Returns:
            The Stripe account ID (acct_xxx)
        """
        if self._account_id is None:
            account = stripe.Account.retrieve()
            self._account_id = account.id
        return self._account_id
    
    def get_payout(self, payout_id: str) -> stripe.Payout:
        """
        Fetch a single payout by ID.
        
        Args:
            payout_id: The Stripe payout ID (po_xxxxx)
            
        Returns:
            Stripe Payout object
        """
        return stripe.Payout.retrieve(payout_id, expand=["destination"])
    
    def list_payouts(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> Generator[stripe.Payout, None, None]:
        """
        List payouts within a date range.
        
        Args:
            from_date: Start date (inclusive)
            to_date: End date (inclusive)
            status: Payout status filter (None = all statuses)
            limit: Number of payouts per page
            
        Yields:
            Stripe Payout objects
        """
        params: Dict[str, Any] = {
            "limit": limit
        }
        
        # Only add status filter if explicitly specified
        if status:
            params["status"] = status
        
        if from_date or to_date:
            params["created"] = {}
            if from_date:
                params["created"]["gte"] = int(from_date.timestamp())
            if to_date:
                # Include the entire end day by setting to end of day (23:59:59)
                to_date_end = to_date.replace(hour=23, minute=59, second=59)
                params["created"]["lte"] = int(to_date_end.timestamp())
        
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
                expand=["customer", "invoice", "balance_transaction", "payment_intent"]
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
    
    def get_credit_note(self, credit_note_id: str) -> Optional[stripe.CreditNote]:
        """
        Fetch a credit note by ID.
        
        Args:
            credit_note_id: The Stripe credit note ID (cn_xxxxx)
            
        Returns:
            Stripe CreditNote object or None if not found
        """
        try:
            return stripe.CreditNote.retrieve(
                credit_note_id,
                expand=["invoice", "customer"]
            )
        except stripe.error.InvalidRequestError:
            return None
    
    def get_credit_notes_for_invoice(self, invoice_id: str) -> List[stripe.CreditNote]:
        """
        Fetch all credit notes associated with an invoice.
        
        Args:
            invoice_id: The Stripe invoice ID
            
        Returns:
            List of CreditNote objects
        """
        try:
            credit_notes = stripe.CreditNote.list(invoice=invoice_id, limit=100)
            return list(credit_notes.auto_paging_iter())
        except stripe.error.InvalidRequestError:
            return []
    
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
                expand=["customer", "invoice", "charges", "latest_charge"]
            )
        except stripe.error.InvalidRequestError:
            return None
    
    def _get_invoice_id_from_object(self, obj: Any) -> Optional[str]:
        """Extract invoice ID from an object that might have invoice field."""
        if not obj:
            return None
        # Could be expanded object with .id or string ID
        if hasattr(obj, 'id'):
            return obj.id
        if isinstance(obj, str) and obj.startswith('in_'):
            return obj
        return None
    
    def _find_invoice_for_payment_intent(self, payment_intent_id: str) -> Optional[stripe.Invoice]:
        """
        Find invoice associated with a PaymentIntent by searching invoices.
        
        This handles the case where the Invoice has the PaymentIntent reference
        but the PaymentIntent doesn't have the Invoice reference.
        """
        try:
            # Search for invoices with this payment_intent
            invoices = stripe.Invoice.search(
                query=f"payment_intent:'{payment_intent_id}'",
                limit=1
            )
            if invoices.data:
                return invoices.data[0]
        except (stripe.error.InvalidRequestError, stripe.error.APIError):
            pass
        return None
    
    def _find_invoice_for_charge(self, charge: stripe.Charge) -> Optional[stripe.Invoice]:
        """
        Find invoice associated with a Charge by searching customer's invoices.
        
        This handles the case where the Invoice references the Charge but
        the Charge doesn't have the Invoice reference (common with SEPA payments).
        """
        if not charge or not charge.customer:
            return None
            
        customer_id = charge.customer if isinstance(charge.customer, str) else charge.customer.id
        charge_id = charge.id
        
        try:
            # List invoices for this customer and find the one with matching charge
            invoices = stripe.Invoice.list(customer=customer_id, limit=100)
            for invoice in invoices.auto_paging_iter():
                invoice_charge_id = None
                if invoice.charge:
                    invoice_charge_id = invoice.charge if isinstance(invoice.charge, str) else invoice.charge.id
                if invoice_charge_id == charge_id:
                    # Found the matching invoice - retrieve with expansions
                    return stripe.Invoice.retrieve(
                        invoice.id,
                        expand=["customer", "charge", "subscription"]
                    )
        except (stripe.error.InvalidRequestError, stripe.error.APIError):
            pass
        return None
    
    def _extract_invoice_from_charge(
        self, 
        charge: stripe.Charge, 
        seen_invoices: set, 
        invoices: List
    ) -> Optional[str]:
        """
        Extract and fetch invoice from a charge if available.
        Tries multiple paths to find the invoice.
        
        Returns:
            Invoice ID if found and added, None otherwise
        """
        invoice_id = None
        
        # Path 1: Check charge.invoice directly (can be string ID or expanded object)
        if charge.invoice:
            invoice_id = self._get_invoice_id_from_object(charge.invoice)
        
        # Path 2: Check payment_intent.invoice
        if not invoice_id and charge.payment_intent:
            # payment_intent could be expanded or string
            if hasattr(charge.payment_intent, 'invoice') and charge.payment_intent.invoice:
                # PaymentIntent is expanded
                invoice_id = self._get_invoice_id_from_object(charge.payment_intent.invoice)
            elif hasattr(charge.payment_intent, 'id') or isinstance(charge.payment_intent, str):
                # PaymentIntent is not expanded, need to fetch it
                pi_id = charge.payment_intent.id if hasattr(charge.payment_intent, 'id') else charge.payment_intent
                try:
                    pi = stripe.PaymentIntent.retrieve(pi_id, expand=["invoice"])
                    if pi and pi.invoice:
                        invoice_id = self._get_invoice_id_from_object(pi.invoice)
                except stripe.error.InvalidRequestError:
                    pass
        
        # Path 3: Search for invoice by payment_intent (reverse lookup)
        if not invoice_id and charge.payment_intent:
            pi_id = charge.payment_intent.id if hasattr(charge.payment_intent, 'id') else charge.payment_intent
            if pi_id:
                found_invoice = self._find_invoice_for_payment_intent(pi_id)
                if found_invoice:
                    invoice_id = found_invoice.id
                    # We already have the invoice object, add it directly
                    if invoice_id not in seen_invoices:
                        invoices.append(found_invoice)
                        seen_invoices.add(invoice_id)
                        return invoice_id
        
        # Path 4: Search customer's invoices for matching charge ID (for SEPA payments)
        # This handles cases where the invoice references the charge but the charge
        # doesn't reference the invoice
        if not invoice_id:
            found_invoice = self._find_invoice_for_charge(charge)
            if found_invoice:
                invoice_id = found_invoice.id
                if invoice_id not in seen_invoices:
                    invoices.append(found_invoice)
                    seen_invoices.add(invoice_id)
                    return invoice_id
        
        # Fetch and add invoice if found (and not already added via Path 3 or 4)
        if invoice_id and invoice_id not in seen_invoices:
            invoice = self.get_invoice(invoice_id)
            if invoice:
                invoices.append(invoice)
                seen_invoices.add(invoice_id)
                return invoice_id
        
        return invoice_id if invoice_id in seen_invoices else None
    
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
        credit_notes = []
        fees_breakdown = []
        
        # Track unique IDs to avoid duplicates
        seen_invoices = set()
        seen_charges = set()
        seen_credit_notes = set()
        
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
                # Handle Charge sources
                if source.startswith("ch_"):
                    if source not in seen_charges:
                        charge = self.get_charge(source)
                        if charge:
                            charges.append(charge)
                            seen_charges.add(source)
                            # Try to find invoice through multiple paths
                            invoice_found = self._extract_invoice_from_charge(charge, seen_invoices, invoices)
                            
                            # If still no invoice found but we have a PaymentIntent, search via PI
                            if not invoice_found and charge.payment_intent:
                                pi_id = charge.payment_intent.id if hasattr(charge.payment_intent, 'id') else charge.payment_intent
                                if pi_id:
                                    found_invoice = self._find_invoice_for_payment_intent(pi_id)
                                    if found_invoice and found_invoice.id not in seen_invoices:
                                        invoices.append(found_invoice)
                                        seen_invoices.add(found_invoice.id)
                
                # Handle Refund sources
                elif source.startswith("re_"):
                    refund = self.get_refund(source)
                    if refund:
                        refunds.append(refund)
                        # Try to get credit note for this refund
                        # A refund might be linked to an invoice through its charge
                        if refund.charge:
                            charge_id = refund.charge.id if hasattr(refund.charge, 'id') else refund.charge
                            # Get the charge to find the invoice
                            if charge_id not in seen_charges:
                                charge = self.get_charge(charge_id)
                                if charge:
                                    seen_charges.add(charge_id)
                                    invoice_id = self._extract_invoice_from_charge(charge, seen_invoices, invoices)
                                    if invoice_id:
                                        # Fetch credit notes for this invoice
                                        inv_credit_notes = self.get_credit_notes_for_invoice(invoice_id)
                                        for cn in inv_credit_notes:
                                            if cn.id not in seen_credit_notes:
                                                credit_notes.append(cn)
                                                seen_credit_notes.add(cn.id)
                
                # Handle Dispute sources
                elif source.startswith("dp_"):
                    dispute = self.get_dispute(source)
                    if dispute:
                        disputes.append(dispute)
                
                # Handle Transfer sources
                elif source.startswith("tr_"):
                    transfer = self.get_transfer(source)
                    if transfer:
                        transfers.append(transfer)
                
                # Handle PaymentIntent sources
                elif source.startswith("pi_"):
                    payment_intent = self.get_payment_intent(source)
                    if payment_intent:
                        invoice_found = False
                        
                        # Path 1: Check if PaymentIntent has direct invoice reference
                        if hasattr(payment_intent, 'invoice') and payment_intent.invoice:
                            invoice_id = self._get_invoice_id_from_object(payment_intent.invoice)
                            if invoice_id and invoice_id not in seen_invoices:
                                invoice = self.get_invoice(invoice_id)
                                if invoice:
                                    invoices.append(invoice)
                                    seen_invoices.add(invoice_id)
                                    invoice_found = True
                        
                        # Path 2: Search for invoice by payment_intent (reverse lookup)
                        if not invoice_found:
                            found_invoice = self._find_invoice_for_payment_intent(source)
                            if found_invoice and found_invoice.id not in seen_invoices:
                                invoices.append(found_invoice)
                                seen_invoices.add(found_invoice.id)
                                invoice_found = True
                        
                        # Extract charges from payment intent
                        if hasattr(payment_intent, 'charges') and payment_intent.charges:
                            for charge in payment_intent.charges.data:
                                if charge.id not in seen_charges:
                                    charges.append(charge)
                                    seen_charges.add(charge.id)
                                    # Still try to extract invoice from charge as backup
                                    if not invoice_found:
                                        self._extract_invoice_from_charge(charge, seen_invoices, invoices)
                        
                        # Also check latest_charge if charges list is empty
                        if hasattr(payment_intent, 'latest_charge') and payment_intent.latest_charge:
                            charge_id = self._get_invoice_id_from_object(payment_intent.latest_charge) or (
                                payment_intent.latest_charge if isinstance(payment_intent.latest_charge, str) else None
                            )
                            # latest_charge could be expanded charge object or string ID
                            if hasattr(payment_intent.latest_charge, 'id'):
                                # It's an expanded charge object
                                charge = payment_intent.latest_charge
                                if charge.id not in seen_charges:
                                    charges.append(charge)
                                    seen_charges.add(charge.id)
                                    if not invoice_found:
                                        self._extract_invoice_from_charge(charge, seen_invoices, invoices)
                            elif isinstance(payment_intent.latest_charge, str):
                                # It's a string ID
                                charge_id = payment_intent.latest_charge
                                if charge_id not in seen_charges:
                                    charge = self.get_charge(charge_id)
                                    if charge:
                                        charges.append(charge)
                                        seen_charges.add(charge_id)
                                        if not invoice_found:
                                            self._extract_invoice_from_charge(charge, seen_invoices, invoices)
                
                # Handle Payment sources (py_ prefix used for some payment methods like SEPA Debit)
                # These are Charge objects with a different ID format
                elif source.startswith("py_"):
                    if source not in seen_charges:
                        charge = self.get_charge(source)
                        if charge:
                            charges.append(charge)
                            seen_charges.add(source)
                            # Try to find invoice through multiple paths
                            invoice_found = self._extract_invoice_from_charge(charge, seen_invoices, invoices)
                            
                            # If still no invoice found but we have a PaymentIntent, search via PI
                            if not invoice_found and charge.payment_intent:
                                pi_id = charge.payment_intent.id if hasattr(charge.payment_intent, 'id') else charge.payment_intent
                                if pi_id:
                                    found_invoice = self._find_invoice_for_payment_intent(pi_id)
                                    if found_invoice and found_invoice.id not in seen_invoices:
                                        invoices.append(found_invoice)
                                        seen_invoices.add(found_invoice.id)
                
                # Handle sources that look like charge IDs but with different format
                # Some older balance transactions might have different formats
                # Also handle payment_failure transactions which may have associated charges/invoices
                elif bt.type in ('charge', 'payment', 'payment_failure') and not source.startswith(('payout', 'po_')):
                    # Try to retrieve as a charge anyway
                    try:
                        charge = stripe.Charge.retrieve(
                            source,
                            expand=["customer", "invoice", "balance_transaction", "payment_intent"]
                        )
                        if charge and charge.id not in seen_charges:
                            charges.append(charge)
                            seen_charges.add(charge.id)
                            invoice_found = self._extract_invoice_from_charge(charge, seen_invoices, invoices)
                            
                            # For payment_failure, also try to find invoice via PaymentIntent
                            if not invoice_found and charge.payment_intent:
                                pi_id = charge.payment_intent.id if hasattr(charge.payment_intent, 'id') else charge.payment_intent
                                if pi_id:
                                    found_invoice = self._find_invoice_for_payment_intent(pi_id)
                                    if found_invoice and found_invoice.id not in seen_invoices:
                                        invoices.append(found_invoice)
                                        seen_invoices.add(found_invoice.id)
                    except stripe.error.InvalidRequestError:
                        pass
        
        return {
            "payout": payout,
            "balance_transactions": balance_transactions,
            "charges": charges,
            "refunds": refunds,
            "invoices": invoices,
            "disputes": disputes,
            "transfers": transfers,
            "credit_notes": credit_notes,
            "fees_breakdown": fees_breakdown,
            "account_id": self.get_account_id()
        }

