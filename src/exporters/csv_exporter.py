"""
CSV Exporter for Stripe payout data
"""

import csv
import os
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any

from ..models import PayoutExportData, TransactionRecord, InvoiceRecord, FeeRecord, RefundRecord, CreditNoteRecord
from ..utils import format_date_fr, format_currency_fr, cents_to_decimal


class CSVExporter:
    """Export payout data to CSV files with French formatting."""
    
    def __init__(self, output_dir: str):
        """
        Initialize CSV exporter.
        
        Args:
            output_dir: Directory to save CSV files
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def _format_decimal_fr(self, value: Decimal) -> str:
        """Format decimal with French number format (comma as decimal separator)."""
        return f"{value:.2f}".replace(".", ",")
    
    def _format_date(self, dt: datetime) -> str:
        """Format datetime for CSV."""
        if dt:
            return format_date_fr(dt)
        return ""
    
    def export_transactions(
        self,
        transactions: List[TransactionRecord],
        filename: str = "transactions.csv"
    ) -> str:
        """
        Export transactions to CSV.
        
        Args:
            transactions: List of TransactionRecord objects
            filename: Output filename
            
        Returns:
            Path to the created file
        """
        filepath = os.path.join(self.output_dir, filename)
        
        headers = [
            "Date",
            "Référence",
            "Type",
            "Description",
            "Montant Brut",
            "Frais",
            "Montant Net",
            "Devise",
            "Client",
            "N° Facture"
        ]
        
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';', quoting=csv.QUOTE_MINIMAL)
            writer.writerow(headers)
            
            for tx in transactions:
                row = [
                    self._format_date(tx.date),
                    tx.reference,
                    tx.type,
                    tx.description,
                    self._format_decimal_fr(tx.montant_brut),
                    self._format_decimal_fr(tx.frais),
                    self._format_decimal_fr(tx.montant_net),
                    tx.devise,
                    tx.client or "",
                    tx.numero_facture or ""
                ]
                writer.writerow(row)
        
        return filepath
    
    def export_invoices(
        self,
        invoices: List[InvoiceRecord],
        filename: str = "factures.csv"
    ) -> str:
        """
        Export invoices to CSV.
        
        Args:
            invoices: List of InvoiceRecord objects
            filename: Output filename
            
        Returns:
            Path to the created file
        """
        filepath = os.path.join(self.output_dir, filename)
        
        headers = [
            "N° Facture",
            "Date",
            "Date Échéance",
            "Client",
            "Email",
            "Montant HT",
            "TVA",
            "Montant TTC",
            "Devise",
            "Statut",
            "ID Stripe"
        ]
        
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';', quoting=csv.QUOTE_MINIMAL)
            writer.writerow(headers)
            
            for inv in invoices:
                row = [
                    inv.numero,
                    self._format_date(inv.date),
                    self._format_date(inv.date_echeance) if inv.date_echeance else "",
                    inv.client_nom,
                    inv.client_email,
                    self._format_decimal_fr(inv.montant_ht),
                    self._format_decimal_fr(inv.montant_tva),
                    self._format_decimal_fr(inv.montant_ttc),
                    inv.devise,
                    inv.statut,
                    inv.stripe_id
                ]
                writer.writerow(row)
        
        return filepath
    
    def export_fees(
        self,
        fees: List[FeeRecord],
        filename: str = "frais.csv"
    ) -> str:
        """
        Export fees breakdown to CSV.
        
        Args:
            fees: List of FeeRecord objects
            filename: Output filename
            
        Returns:
            Path to the created file
        """
        filepath = os.path.join(self.output_dir, filename)
        
        headers = [
            "Transaction",
            "Type",
            "Description",
            "Montant",
            "Devise"
        ]
        
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';', quoting=csv.QUOTE_MINIMAL)
            writer.writerow(headers)
            
            for fee in fees:
                row = [
                    fee.transaction_id,
                    fee.type,
                    fee.description,
                    self._format_decimal_fr(fee.montant),
                    fee.devise
                ]
                writer.writerow(row)
        
        return filepath
    
    def export_summary(
        self,
        data: PayoutExportData,
        filename: str = "resume.csv"
    ) -> str:
        """
        Export payout summary to CSV.
        
        Args:
            data: PayoutExportData object
            filename: Output filename
            
        Returns:
            Path to the created file
        """
        filepath = os.path.join(self.output_dir, filename)
        summary = data.summary
        
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';', quoting=csv.QUOTE_MINIMAL)
            
            # Write as key-value pairs
            rows = [
                ["Récapitulatif du Virement", ""],
                ["", ""],
                ["ID Payout", summary.payout_id],
                ["Date", self._format_date(summary.date)],
                ["Date Arrivée", self._format_date(summary.date_arrivee)],
                ["Montant", f"{self._format_decimal_fr(summary.montant)} {summary.devise}"],
                ["Statut", summary.statut],
                ["Méthode", summary.methode],
                ["Banque", summary.banque],
                ["", ""],
                ["Détail des Mouvements", ""],
                ["", ""],
                ["Total Paiements", f"{self._format_decimal_fr(summary.total_paiements)} {summary.devise}"],
                ["Total Remboursements", f"{self._format_decimal_fr(summary.total_remboursements)} {summary.devise}"],
                ["Total Frais Stripe", f"{self._format_decimal_fr(summary.total_frais)} {summary.devise}"],
                ["Total Litiges", f"{self._format_decimal_fr(summary.total_litiges)} {summary.devise}"],
                ["Total Échecs Paiement", f"{self._format_decimal_fr(summary.total_echecs_paiement)} {summary.devise}"],
                ["Total Autres", f"{self._format_decimal_fr(summary.total_autres)} {summary.devise}"],
                ["", ""],
                ["Statistiques", ""],
                ["", ""],
                ["Nombre de Transactions", str(summary.nb_transactions)],
                ["Nombre de Factures", str(summary.nb_factures)],
                ["Nombre de Remboursements", str(summary.nb_remboursements)],
                ["Nombre de Litiges", str(summary.nb_litiges)],
                ["Nombre d'Avoirs", str(len(data.credit_notes))],
            ]
            
            for row in rows:
                writer.writerow(row)
        
        return filepath
    
    def export_refunds(
        self,
        refunds: List[RefundRecord],
        filename: str = "remboursements.csv"
    ) -> str:
        """
        Export refunds to CSV.
        
        Args:
            refunds: List of RefundRecord objects
            filename: Output filename
            
        Returns:
            Path to the created file
        """
        filepath = os.path.join(self.output_dir, filename)
        
        headers = [
            "Date",
            "ID Remboursement",
            "Montant",
            "Devise",
            "Statut",
            "Raison",
            "Client",
            "N° Facture",
            "ID Charge",
            "N° Avoir"
        ]
        
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';', quoting=csv.QUOTE_MINIMAL)
            writer.writerow(headers)
            
            for ref in refunds:
                row = [
                    self._format_date(ref.date),
                    ref.refund_id,
                    self._format_decimal_fr(ref.montant),
                    ref.devise,
                    ref.statut,
                    ref.raison or "",
                    ref.client_nom or "",
                    ref.invoice_number or "",
                    ref.charge_id or "",
                    ref.credit_note_number or ""
                ]
                writer.writerow(row)
        
        return filepath
    
    def export_credit_notes(
        self,
        credit_notes: List[CreditNoteRecord],
        filename: str = "avoirs.csv"
    ) -> str:
        """
        Export credit notes to CSV.
        
        Args:
            credit_notes: List of CreditNoteRecord objects
            filename: Output filename
            
        Returns:
            Path to the created file
        """
        filepath = os.path.join(self.output_dir, filename)
        
        headers = [
            "N° Avoir",
            "Date",
            "N° Facture Origine",
            "Client",
            "Email",
            "Montant",
            "Devise",
            "Statut",
            "Raison",
            "ID Stripe"
        ]
        
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';', quoting=csv.QUOTE_MINIMAL)
            writer.writerow(headers)
            
            for cn in credit_notes:
                row = [
                    cn.numero,
                    self._format_date(cn.date),
                    cn.invoice_number or "",
                    cn.client_nom,
                    cn.client_email,
                    self._format_decimal_fr(cn.montant),
                    cn.devise,
                    cn.statut,
                    cn.raison or "",
                    cn.stripe_id
                ]
                writer.writerow(row)
        
        return filepath
    
    def export_all(self, data: PayoutExportData) -> Dict[str, str]:
        """
        Export all data to CSV files.
        
        Args:
            data: PayoutExportData object
            
        Returns:
            Dictionary of export type to file path
        """
        results = {}
        
        results['summary'] = self.export_summary(data)
        results['transactions'] = self.export_transactions(data.transactions)
        
        if data.invoices:
            results['invoices'] = self.export_invoices(data.invoices)
        
        if data.fees:
            results['fees'] = self.export_fees(data.fees)
        
        if data.refunds:
            results['refunds'] = self.export_refunds(data.refunds)
        
        if data.credit_notes:
            results['credit_notes'] = self.export_credit_notes(data.credit_notes)
        
        return results

