"""
Stripe Comptable Export - Main CLI Entry Point

Export des données comptables Stripe pour justification auprès d'un comptable français.
"""

import os
import sys
import shutil
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
import zipfile

import click
from dotenv import load_dotenv

from .stripe_client import StripeClient
from .models import (
    PayoutExportData, PayoutSummary, TransactionRecord,
    InvoiceRecord, FeeRecord
)
from .exporters import CSVExporter, ExcelExporter, PDFExporter
from .invoice_downloader import InvoiceDownloader
from .utils import (
    timestamp_to_datetime, translate_transaction_type,
    translate_invoice_status, translate_payout_status,
    translate_fee_type, get_customer_display_name,
    safe_get, cents_to_decimal, get_bank_account_display,
    sanitize_filename, ensure_dir
)


# Load environment variables
load_dotenv('.env.local')
load_dotenv('.env')


def process_payout_data(raw_data: Dict[str, Any]) -> PayoutExportData:
    """
    Process raw Stripe data into export-ready format.
    
    Args:
        raw_data: Dictionary from StripeClient.get_payout_details()
        
    Returns:
        PayoutExportData object ready for export
    """
    payout = raw_data['payout']
    balance_transactions = raw_data['balance_transactions']
    charges = raw_data['charges']
    refunds = raw_data['refunds']
    invoices = raw_data['invoices']
    disputes = raw_data['disputes']
    fees_breakdown = raw_data['fees_breakdown']
    
    # Process transactions
    transactions: List[TransactionRecord] = []
    
    # Aggregation variables
    total_paiements = Decimal(0)
    total_remboursements = Decimal(0)
    total_frais = Decimal(0)
    total_litiges = Decimal(0)
    total_autres = Decimal(0)
    
    for bt in balance_transactions:
        # Get related invoice number if available
        invoice_number = None
        customer_name = None
        
        # Try to find associated charge for customer/invoice info
        source_id = bt.source
        if source_id:
            for charge in charges:
                if charge.id == source_id:
                    customer_name = get_customer_display_name(charge.customer)
                    if charge.invoice:
                        for inv in invoices:
                            if inv.id == charge.invoice:
                                invoice_number = inv.number
                                break
                    break
        
        # Create transaction record
        tx = TransactionRecord(
            date=timestamp_to_datetime(bt.created),
            reference=bt.id,
            type=translate_transaction_type(bt.type),
            description=bt.description or "",
            montant_brut=cents_to_decimal(bt.amount),
            frais=cents_to_decimal(bt.fee),
            montant_net=cents_to_decimal(bt.net),
            devise=bt.currency.upper(),
            client=customer_name,
            numero_facture=invoice_number
        )
        transactions.append(tx)
        
        # Aggregate by type
        if bt.type in ('charge', 'payment'):
            total_paiements += cents_to_decimal(bt.amount)
        elif bt.type == 'refund':
            total_remboursements += abs(cents_to_decimal(bt.amount))
        elif bt.type in ('stripe_fee', 'application_fee'):
            total_frais += abs(cents_to_decimal(bt.fee))
        elif bt.type in ('dispute', 'dispute_won', 'dispute_lost'):
            total_litiges += abs(cents_to_decimal(bt.amount))
        else:
            total_autres += cents_to_decimal(bt.amount)
        
        # Always track fees
        total_frais += abs(cents_to_decimal(bt.fee))
    
    # Process invoices
    invoice_records: List[InvoiceRecord] = []
    for inv in invoices:
        customer = inv.customer
        customer_name = get_customer_display_name(customer)
        customer_email = safe_get(customer, 'email', default='')
        
        # Calculate amounts
        subtotal = cents_to_decimal(inv.subtotal or 0)
        tax = cents_to_decimal(inv.tax or 0)
        total = cents_to_decimal(inv.total or 0)
        
        inv_record = InvoiceRecord(
            numero=inv.number or inv.id,
            date=timestamp_to_datetime(inv.created),
            date_echeance=timestamp_to_datetime(inv.due_date) if inv.due_date else None,
            client_nom=customer_name,
            client_email=customer_email,
            montant_ht=subtotal,
            montant_tva=tax,
            montant_ttc=total,
            devise=inv.currency.upper(),
            statut=translate_invoice_status(inv.status or 'unknown'),
            pdf_url=inv.invoice_pdf,
            stripe_id=inv.id
        )
        invoice_records.append(inv_record)
    
    # Process fees
    fee_records: List[FeeRecord] = []
    for fee in fees_breakdown:
        fee_record = FeeRecord(
            transaction_id=fee['transaction_id'],
            type=translate_fee_type(fee['type']),
            description=fee['description'] or "",
            montant=cents_to_decimal(fee['amount']),
            devise=fee['currency'].upper()
        )
        fee_records.append(fee_record)
    
    # Create summary
    bank_info = ""
    if hasattr(payout, 'destination') and payout.destination:
        bank_info = get_bank_account_display(payout.destination)
    
    summary = PayoutSummary(
        payout_id=payout.id,
        date=timestamp_to_datetime(payout.created),
        date_arrivee=timestamp_to_datetime(payout.arrival_date),
        montant=cents_to_decimal(payout.amount),
        devise=payout.currency.upper(),
        statut=translate_payout_status(payout.status),
        methode=payout.method or "standard",
        banque=bank_info,
        total_paiements=total_paiements,
        total_remboursements=total_remboursements,
        total_frais=total_frais,
        total_litiges=total_litiges,
        total_autres=total_autres,
        nb_transactions=len(transactions),
        nb_factures=len(invoice_records),
        nb_remboursements=len(refunds),
        nb_litiges=len(disputes)
    )
    
    return PayoutExportData(
        summary=summary,
        transactions=transactions,
        invoices=invoice_records,
        fees=fee_records,
        raw_data=raw_data
    )


def create_zip_archive(source_dir: str, output_path: str) -> str:
    """
    Create a ZIP archive of the export directory.
    
    Args:
        source_dir: Directory to archive
        output_path: Path for the ZIP file
        
    Returns:
        Path to the created ZIP file
    """
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, source_dir)
                zipf.write(file_path, arcname)
    
    return output_path


def export_payout(
    payout_id: str,
    client: StripeClient,
    base_output_dir: str,
    download_invoices: bool = True
) -> str:
    """
    Export a single payout to a zipped folder.
    
    Args:
        payout_id: Stripe payout ID
        client: StripeClient instance
        base_output_dir: Base output directory
        download_invoices: Whether to download invoice PDFs
        
    Returns:
        Path to the created ZIP file
    """
    click.echo(f"\n{'='*60}")
    click.echo(f"Traitement du virement: {payout_id}")
    click.echo('='*60)
    
    # Fetch data
    click.echo("📥 Récupération des données Stripe...")
    raw_data = client.get_payout_details(payout_id)
    
    # Process data
    click.echo("🔄 Traitement des données...")
    export_data = process_payout_data(raw_data)
    
    # Create output directory for this payout
    payout_date = export_data.summary.date.strftime("%Y%m%d")
    folder_name = sanitize_filename(f"payout_{payout_date}_{payout_id}")
    payout_dir = os.path.join(base_output_dir, folder_name)
    ensure_dir(payout_dir)
    
    # Export to CSV
    click.echo("📄 Export CSV...")
    csv_exporter = CSVExporter(payout_dir)
    csv_exporter.export_all(export_data)
    
    # Export to Excel
    click.echo("📊 Export Excel...")
    excel_exporter = ExcelExporter(payout_dir)
    excel_exporter.export(export_data)
    
    # Export to PDF
    click.echo("📑 Génération du rapport PDF...")
    pdf_exporter = PDFExporter(payout_dir)
    pdf_exporter.export(export_data)
    
    # Download invoice PDFs
    if download_invoices and export_data.invoices:
        click.echo("📎 Téléchargement des factures PDF...")
        downloader = InvoiceDownloader(payout_dir)
        downloader.download_all(export_data.invoices)
    
    # Create ZIP archive
    click.echo("🗜️  Création de l'archive ZIP...")
    zip_path = os.path.join(base_output_dir, f"{folder_name}.zip")
    create_zip_archive(payout_dir, zip_path)
    
    # Optionally remove the unzipped folder
    # shutil.rmtree(payout_dir)
    
    click.echo(f"\n✅ Export terminé: {zip_path}")
    click.echo(f"   Transactions: {export_data.summary.nb_transactions}")
    click.echo(f"   Factures: {export_data.summary.nb_factures}")
    click.echo(f"   Montant: {export_data.summary.montant} {export_data.summary.devise}")
    
    return zip_path


@click.command()
@click.option(
    '--payout', '-p',
    help='ID du payout Stripe (ex: po_xxxxx)'
)
@click.option(
    '--from', 'from_date',
    help='Date de début (format: YYYY-MM-DD)',
    type=click.DateTime(formats=["%Y-%m-%d"])
)
@click.option(
    '--to', 'to_date',
    help='Date de fin (format: YYYY-MM-DD)',
    type=click.DateTime(formats=["%Y-%m-%d"])
)
@click.option(
    '--output', '-o',
    default=None,
    help='Répertoire de sortie (défaut: ./output)'
)
@click.option(
    '--no-invoices',
    is_flag=True,
    default=False,
    help='Ne pas télécharger les factures PDF'
)
@click.option(
    '--api-key', '-k',
    envvar='STRIPE_API_KEY',
    help='Clé API Stripe (ou variable STRIPE_API_KEY)'
)
def main(
    payout: Optional[str],
    from_date: Optional[datetime],
    to_date: Optional[datetime],
    output: Optional[str],
    no_invoices: bool,
    api_key: Optional[str]
):
    """
    Stripe Comptable Export - Export des données comptables Stripe.
    
    Génère des fichiers CSV, Excel et PDF pour justification comptable,
    avec téléchargement des factures PDF associées.
    
    Exemples d'utilisation:
    
    \b
    # Export d'un seul payout
    python -m src.main --payout po_xxxxx
    
    \b
    # Export de tous les payouts sur une période
    python -m src.main --from 2024-01-01 --to 2024-12-31
    
    \b
    # Export avec répertoire personnalisé
    python -m src.main --payout po_xxxxx --output ./exports
    """
    click.echo("""
╔═══════════════════════════════════════════════════════════════╗
║           STRIPE COMPTABLE EXPORT v1.0                        ║
║     Export des données comptables pour justification          ║
╚═══════════════════════════════════════════════════════════════╝
    """)
    
    # Validate arguments
    if not payout and not (from_date or to_date):
        click.echo("❌ Erreur: Spécifiez --payout ou --from/--to", err=True)
        click.echo("   Utilisez --help pour plus d'informations.", err=True)
        sys.exit(1)
    
    if (from_date and not to_date) or (to_date and not from_date):
        click.echo("❌ Erreur: --from et --to doivent être utilisés ensemble", err=True)
        sys.exit(1)
    
    # Setup output directory
    output_dir = output or os.getenv('OUTPUT_DIR', './output')
    ensure_dir(output_dir)
    click.echo(f"📁 Répertoire de sortie: {os.path.abspath(output_dir)}")
    
    # Initialize Stripe client
    try:
        client = StripeClient(api_key)
        click.echo("✓ Connexion Stripe établie")
    except ValueError as e:
        click.echo(f"❌ Erreur: {e}", err=True)
        sys.exit(1)
    
    download_invoices = not no_invoices
    exported_files = []
    
    try:
        if payout:
            # Single payout mode
            zip_path = export_payout(payout, client, output_dir, download_invoices)
            exported_files.append(zip_path)
        else:
            # Date range mode
            click.echo(f"\n📅 Recherche des payouts du {from_date.strftime('%d/%m/%Y')} au {to_date.strftime('%d/%m/%Y')}...")
            
            payouts = list(client.list_payouts(from_date, to_date))
            
            if not payouts:
                click.echo("ℹ️  Aucun payout trouvé pour cette période.")
                sys.exit(0)
            
            click.echo(f"✓ {len(payouts)} payout(s) trouvé(s)")
            
            for p in payouts:
                try:
                    zip_path = export_payout(p.id, client, output_dir, download_invoices)
                    exported_files.append(zip_path)
                except Exception as e:
                    click.echo(f"❌ Erreur pour {p.id}: {e}", err=True)
                    continue
        
        # Summary
        click.echo(f"\n{'='*60}")
        click.echo("RÉCAPITULATIF")
        click.echo('='*60)
        click.echo(f"✅ {len(exported_files)} export(s) créé(s):")
        for f in exported_files:
            click.echo(f"   • {f}")
        
    except Exception as e:
        click.echo(f"\n❌ Erreur fatale: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    main()

