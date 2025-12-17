"""
Invoice PDF Downloader for Stripe invoices
"""

import os
import requests
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from .models import InvoiceRecord
from .utils import sanitize_filename, ensure_dir


class InvoiceDownloader:
    """Download invoice PDFs from Stripe."""
    
    def __init__(self, output_dir: str, max_workers: int = 5):
        """
        Initialize the invoice downloader.
        
        Args:
            output_dir: Directory to save downloaded PDFs
            max_workers: Maximum concurrent downloads
        """
        self.output_dir = ensure_dir(os.path.join(output_dir, "factures"))
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
            
            filepath = os.path.join(self.output_dir, filename)
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            return filepath
            
        except requests.RequestException as e:
            print(f"Erreur téléchargement facture {invoice.numero}: {e}")
            return None
        except IOError as e:
            print(f"Erreur écriture facture {invoice.numero}: {e}")
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

