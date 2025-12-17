"""
Invoice PDF Downloader for Stripe invoices and credit notes
"""

import os
import requests
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from .models import InvoiceRecord, CreditNoteRecord
from .utils import sanitize_filename, ensure_dir


class InvoiceDownloader:
    """Download invoice and credit note PDFs from Stripe."""
    
    def __init__(self, output_dir: str, max_workers: int = 5):
        """
        Initialize the invoice downloader.
        
        Args:
            output_dir: Directory to save downloaded PDFs
            max_workers: Maximum concurrent downloads
        """
        self.output_dir = output_dir
        self.invoices_dir = ensure_dir(os.path.join(output_dir, "factures"))
        self.credit_notes_dir = ensure_dir(os.path.join(output_dir, "avoirs"))
        self.max_workers = max_workers
    
    def _download_single(self, invoice: InvoiceRecord) -> Optional[str]:
        """
        Download a single invoice PDF.
        
        Args:
            invoice: InvoiceRecord with PDF URL
            
        Returns:
            Path to downloaded file or None if failed
        """
        if not invoice.pdf_url:
            return None
        
        try:
            response = requests.get(invoice.pdf_url, timeout=30)
            response.raise_for_status()
            
            # Create filename from invoice number
            filename = sanitize_filename(f"{invoice.numero}.pdf")
            if not filename.endswith('.pdf'):
                filename = f"{filename}.pdf"
            
            filepath = os.path.join(self.invoices_dir, filename)
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            return filepath
            
        except requests.RequestException as e:
            print(f"Erreur téléchargement facture {invoice.numero}: {e}")
            return None
        except IOError as e:
            print(f"Erreur écriture facture {invoice.numero}: {e}")
            return None
    
    def _download_credit_note(self, credit_note: CreditNoteRecord) -> Optional[str]:
        """
        Download a single credit note PDF.
        
        Args:
            credit_note: CreditNoteRecord with PDF URL
            
        Returns:
            Path to downloaded file or None if failed
        """
        if not credit_note.pdf_url:
            return None
        
        try:
            response = requests.get(credit_note.pdf_url, timeout=30)
            response.raise_for_status()
            
            # Create filename from credit note number
            filename = sanitize_filename(f"avoir_{credit_note.numero}.pdf")
            if not filename.endswith('.pdf'):
                filename = f"{filename}.pdf"
            
            filepath = os.path.join(self.credit_notes_dir, filename)
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            return filepath
            
        except requests.RequestException as e:
            print(f"Erreur téléchargement avoir {credit_note.numero}: {e}")
            return None
        except IOError as e:
            print(f"Erreur écriture avoir {credit_note.numero}: {e}")
            return None
    
    def download_all(self, invoices: List[InvoiceRecord]) -> Dict[str, str]:
        """
        Download all invoice PDFs.
        
        Args:
            invoices: List of InvoiceRecord objects with PDF URLs
            
        Returns:
            Dictionary mapping invoice number to file path
        """
        results = {}
        
        # Filter invoices with PDF URLs
        invoices_with_pdf = [inv for inv in invoices if inv.pdf_url]
        
        if not invoices_with_pdf:
            print("Aucune facture PDF à télécharger.")
            return results
        
        print(f"Téléchargement de {len(invoices_with_pdf)} factures PDF...")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_invoice = {
                executor.submit(self._download_single, inv): inv
                for inv in invoices_with_pdf
            }
            
            for future in as_completed(future_to_invoice):
                invoice = future_to_invoice[future]
                try:
                    filepath = future.result()
                    if filepath:
                        results[invoice.numero] = filepath
                        print(f"  ✓ {invoice.numero}")
                    else:
                        print(f"  ✗ {invoice.numero} (pas de PDF)")
                except Exception as e:
                    print(f"  ✗ {invoice.numero} (erreur: {e})")
        
        print(f"Téléchargement terminé: {len(results)}/{len(invoices_with_pdf)} factures")
        return results
    
    def download_single_invoice(self, invoice: InvoiceRecord) -> Optional[str]:
        """
        Download a single invoice PDF (public method).
        
        Args:
            invoice: InvoiceRecord with PDF URL
            
        Returns:
            Path to downloaded file or None if failed
        """
        return self._download_single(invoice)
    
    def download_all_credit_notes(self, credit_notes: List[CreditNoteRecord]) -> Dict[str, str]:
        """
        Download all credit note PDFs.
        
        Args:
            credit_notes: List of CreditNoteRecord objects with PDF URLs
            
        Returns:
            Dictionary mapping credit note number to file path
        """
        results = {}
        
        # Filter credit notes with PDF URLs
        notes_with_pdf = [cn for cn in credit_notes if cn.pdf_url]
        
        if not notes_with_pdf:
            return results
        
        print(f"Téléchargement de {len(notes_with_pdf)} avoirs PDF...")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_note = {
                executor.submit(self._download_credit_note, cn): cn
                for cn in notes_with_pdf
            }
            
            for future in as_completed(future_to_note):
                credit_note = future_to_note[future]
                try:
                    filepath = future.result()
                    if filepath:
                        results[credit_note.numero] = filepath
                        print(f"  ✓ Avoir {credit_note.numero}")
                    else:
                        print(f"  ✗ Avoir {credit_note.numero} (pas de PDF)")
                except Exception as e:
                    print(f"  ✗ Avoir {credit_note.numero} (erreur: {e})")
        
        print(f"Téléchargement terminé: {len(results)}/{len(notes_with_pdf)} avoirs")
        return results

