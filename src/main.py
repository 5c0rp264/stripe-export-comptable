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
    InvoiceRecord, FeeRecord, RefundRecord, CreditNoteRecord
)
from .exporters import CSVExporter, ExcelExporter, PDFExporter
from .invoice_downloader import InvoiceDownloader
from .utils import (
    timestamp_to_datetime, translate_transaction_type,
    translate_invoice_status, translate_payout_status,
    translate_fee_type, translate_refund_reason, translate_refund_status,
    translate_credit_note_status, get_customer_display_name,
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
    credit_notes = raw_data.get('credit_notes', [])
    fees_breakdown = raw_data['fees_breakdown']
    
    # Process transactions
    transactions: List[TransactionRecord] = []
    
    # Aggregation variables
    total_paiements = Decimal(0)
    total_remboursements = Decimal(0)
    total_frais = Decimal(0)
    total_litiges = Decimal(0)
    total_echecs_paiement = Decimal(0)  # Payment failures
    total_autres = Decimal(0)
    
    for bt in balance_transactions:
        # Skip payout transactions - the report IS about the payout, 
        # so we don't include the payout itself in the transactions list
        if bt.type in ('payout', 'payout_failure'):
            continue
        
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
                        # charge.invoice can be a string ID or an expanded Invoice object
                        charge_invoice_id = charge.invoice.id if hasattr(charge.invoice, 'id') else charge.invoice
                        for inv in invoices:
                            if inv.id == charge_invoice_id:
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
            numero_facture=invoice_number,
            source_id=source_id  # Store source object ID for dashboard links
        )
        transactions.append(tx)
        
        # Aggregate by type (payout transactions are already skipped above)
        if bt.type in ('charge', 'payment'):
            total_paiements += cents_to_decimal(bt.amount)
            # Add processing fees from this transaction
            total_frais += abs(cents_to_decimal(bt.fee))
        elif bt.type in ('payment_failure', 'payment_failure_refund'):
            # Payment failures and their refunds are tracked separately
            total_echecs_paiement += abs(cents_to_decimal(bt.amount))
            # Track any fees on payment failures
            if bt.fee != 0:
                total_frais += abs(cents_to_decimal(bt.fee))
        elif bt.type == 'refund':
            total_remboursements += abs(cents_to_decimal(bt.amount))
            # Refunds may have fee reversals (negative fees) - track if any
            if bt.fee != 0:
                total_frais += abs(cents_to_decimal(bt.fee))
        elif bt.type in ('stripe_fee', 'application_fee'):
            # For stripe_fee transactions, the fee amount is in bt.amount (not bt.fee)
            # These are separate charges like Billing fees, Automatic Tax fees, etc.
            total_frais += abs(cents_to_decimal(bt.amount))
        elif bt.type in ('dispute', 'dispute_won', 'dispute_lost'):
            total_litiges += abs(cents_to_decimal(bt.amount))
            # Disputes may have fees
            if bt.fee != 0:
                total_frais += abs(cents_to_decimal(bt.fee))
        else:
            total_autres += cents_to_decimal(bt.amount)
            # Track any fees on other transaction types
            if bt.fee != 0:
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
    
    # Process refunds
    refund_records: List[RefundRecord] = []
    for ref in refunds:
        # Try to find related invoice number
        invoice_number = None
        client_name = None
        
        if ref.charge:
            charge_id = ref.charge.id if hasattr(ref.charge, 'id') else ref.charge
            # Find the charge to get invoice info
            for charge in charges:
                if charge.id == charge_id:
                    client_name = get_customer_display_name(charge.customer)
                    if charge.invoice:
                        charge_invoice_id = charge.invoice.id if hasattr(charge.invoice, 'id') else charge.invoice
                        for inv in invoices:
                            if inv.id == charge_invoice_id:
                                invoice_number = inv.number
                                break
                    break
        
        refund_record = RefundRecord(
            refund_id=ref.id,
            date=timestamp_to_datetime(ref.created),
            montant=cents_to_decimal(ref.amount),
            devise=ref.currency.upper(),
            statut=translate_refund_status(ref.status),
            raison=translate_refund_reason(ref.reason),
            charge_id=ref.charge.id if hasattr(ref.charge, 'id') else ref.charge if ref.charge else None,
            invoice_number=invoice_number,
            client_nom=client_name
        )
        refund_records.append(refund_record)
    
    # Process credit notes
    credit_note_records: List[CreditNoteRecord] = []
    for cn in credit_notes:
        customer = cn.customer
        customer_name = get_customer_display_name(customer)
        customer_email = safe_get(customer, 'email', default='')
        
        # Get invoice number if available
        invoice_number = None
        if cn.invoice:
            invoice_id = cn.invoice.id if hasattr(cn.invoice, 'id') else cn.invoice
            for inv in invoices:
                if inv.id == invoice_id:
                    invoice_number = inv.number
                    break
        
        cn_record = CreditNoteRecord(
            numero=cn.number or cn.id,
            date=timestamp_to_datetime(cn.created),
            invoice_number=invoice_number,
            client_nom=customer_name,
            client_email=customer_email,
            montant=cents_to_decimal(cn.total),
            devise=cn.currency.upper(),
            statut=translate_credit_note_status(cn.status or 'issued'),
            raison=cn.reason or None,
            pdf_url=cn.pdf,
            stripe_id=cn.id
        )
        credit_note_records.append(cn_record)
    
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
        total_echecs_paiement=total_echecs_paiement,
        total_autres=total_autres,
        nb_transactions=len(transactions),
        nb_factures=len(invoice_records),
        nb_remboursements=len(refunds),
        nb_litiges=len(disputes)
    )
    
    # Get account ID for dashboard URLs
    account_id = raw_data.get('account_id')
    
    return PayoutExportData(
        summary=summary,
        transactions=transactions,
        invoices=invoice_records,
        fees=fee_records,
        refunds=refund_records,
        credit_notes=credit_note_records,
        raw_data=raw_data,
        account_id=account_id
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


def create_complete_export_zip(output_dir: str, payout_folders: List[str]) -> str:
    """
    Create a complete export ZIP containing the GUIDE, all payout folders,
    and the factures_stripe folder.
    
    Args:
        output_dir: Base output directory
        payout_folders: List of payout folder names that were processed
        
    Returns:
        Path to the created ZIP file
    """
    zip_path = os.path.join(output_dir, "export_comptable_complet.zip")
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Add the GUIDE PDF
        guide_path = os.path.join(output_dir, "GUIDE_Factures_Stripe.pdf")
        if os.path.exists(guide_path):
            zipf.write(guide_path, "GUIDE_Factures_Stripe.pdf")
        
        # Add all payout folders
        for folder_name in payout_folders:
            folder_path = os.path.join(output_dir, folder_name)
            if os.path.isdir(folder_path):
                for root, dirs, files in os.walk(folder_path):
                    # Add directory entries for empty directories
                    for dir_name in dirs:
                        dir_path = os.path.join(root, dir_name)
                        arcname = os.path.relpath(dir_path, output_dir) + '/'
                        zipf.write(dir_path, arcname)
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, output_dir)
                        zipf.write(file_path, arcname)
        
        # Add the factures_stripe folder (even if empty)
        factures_stripe_dir = os.path.join(output_dir, "factures_stripe")
        if os.path.isdir(factures_stripe_dir):
            # Add the empty folder entry
            zipf.writestr("factures_stripe/", "")
            # Add any files if present
            for root, dirs, files in os.walk(factures_stripe_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, output_dir)
                    zipf.write(file_path, arcname)
    
    return zip_path


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
    
    # Download credit note PDFs (refund proofs)
    if download_invoices and export_data.credit_notes:
        click.echo("📎 Téléchargement des avoirs PDF (preuves de remboursement)...")
        downloader = InvoiceDownloader(payout_dir)
        downloader.download_all_credit_notes(export_data.credit_notes)
    
    # Create ZIP archive
    click.echo("🗜️  Création de l'archive ZIP...")
    zip_path = os.path.join(base_output_dir, f"{folder_name}.zip")
    create_zip_archive(payout_dir, zip_path)
    
    # Optionally remove the unzipped folder
    # shutil.rmtree(payout_dir)
    
    click.echo(f"\n✅ Export terminé: {zip_path}")
    click.echo(f"   Transactions: {export_data.summary.nb_transactions}")
    click.echo(f"   Factures: {export_data.summary.nb_factures}")
    click.echo(f"   Remboursements: {export_data.summary.nb_remboursements}")
    if export_data.credit_notes:
        click.echo(f"   Avoirs: {len(export_data.credit_notes)}")
    click.echo(f"   Montant: {export_data.summary.montant} {export_data.summary.devise}")
    
    return zip_path


def generate_stripe_invoices_guide(output_dir: str) -> str:
    """
    Generate a PDF guide explaining how to download Stripe billing invoices.
    Also creates the frais_stripe folder in the output directory.
    
    Args:
        output_dir: Base output directory
        
    Returns:
        Path to the created PDF guide
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.enums import TA_CENTER
    
    # Create frais_stripe folder
    frais_stripe_dir = os.path.join(output_dir, "factures_stripe")
    ensure_dir(frais_stripe_dir)
    
    # Create PDF guide
    pdf_path = os.path.join(output_dir, "GUIDE_Factures_Stripe.pdf")
    
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        name='CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor("#1F4E79"),
        alignment=TA_CENTER,
        spaceAfter=20,
        spaceBefore=10
    )
    
    heading_style = ParagraphStyle(
        name='CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor("#1F4E79"),
        spaceBefore=15,
        spaceAfter=10
    )
    
    body_style = ParagraphStyle(
        name='CustomBody',
        parent=styles['Normal'],
        fontSize=11,
        spaceBefore=6,
        spaceAfter=6,
        leading=14
    )
    
    elements = []
    
    # Title
    elements.append(Paragraph(
        "GUIDE : Télécharger les factures Stripe",
        title_style
    ))
    
    elements.append(Spacer(1, 20))
    
    # Introduction
    elements.append(Paragraph(
        "Ce guide explique comment télécharger les factures mensuelles de frais Stripe. "
        "Ces documents sont <b>indispensables</b> pour la comptabilisation des charges liées aux services Stripe.",
        body_style
    ))
    
    elements.append(Spacer(1, 15))
    
    # What are these invoices
    elements.append(Paragraph("Qu'est-ce que ces factures ?", heading_style))
    elements.append(Paragraph(
        "Stripe émet chaque mois une facture récapitulant les frais prélevés sur vos transactions : "
        "frais de traitement des paiements, frais de services additionnels (Radar, Tax, etc.), "
        "et autres commissions. Ces factures constituent les justificatifs comptables des charges Stripe qui sont mentionnées dans chacun des rapports de virement exportés.",
        body_style
    ))
    
    elements.append(Spacer(1, 15))
    
    # Steps
    elements.append(Paragraph("Procédure de téléchargement", heading_style))
    
    steps = [
        ["Étape 1", "Connectez-vous à votre tableau de bord Stripe : https://dashboard.stripe.com"],
        ["Étape 2", "Cliquez sur l'icône Paramètres (engrenage) en haut à droite"],
        ["Étape 3", "Dans le menu, trouvez la section « Conformité et justificatifs »"],
        ["Étape 4", "Cliquez sur « Mes documents »"],
        ["Étape 5", "Téléchargez les factures des mois concernés par vos virements"],
        ["Étape 6", "Placez les fichiers PDF dans le dossier « factures_stripe » de ce répertoire"],
    ]
    
    step_table = Table(steps, colWidths=[2.5*cm, 13*cm])
    step_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor("#1F4E79")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.HexColor("#F2F2F2"), colors.white]),
    ]))
    
    elements.append(step_table)
    
    elements.append(Spacer(1, 20))
    
    # Important note
    elements.append(Paragraph("Important", heading_style))
    elements.append(Paragraph(
        "Les factures Stripe sont émises mensuellement. Pour chaque virement exporté, "
        "vérifiez les mois concernés par les transactions (indiqués dans le rapport comptable PDF) "
        "et téléchargez les factures correspondantes.",
        body_style
    ))
    
    elements.append(Spacer(1, 15))
    
    # Folder structure
    elements.append(Paragraph("Organisation des fichiers", heading_style))
    elements.append(Paragraph(
        "Placez les factures Stripe téléchargées dans le dossier :",
        body_style
    ))
    elements.append(Paragraph(
        "<b>factures_stripe/</b>",
        ParagraphStyle(
            name='FolderPath',
            parent=styles['Normal'],
            fontSize=12,
            fontName='Courier',
            leftIndent=20,
            spaceBefore=10,
            spaceAfter=10,
            backColor=colors.HexColor("#F2F2F2")
        )
    ))
    elements.append(Paragraph(
        "Ce dossier a été créé automatiquement dans le répertoire d'export.",
        body_style
    ))
    
    elements.append(Spacer(1, 30))
    
    # Footer
    elements.append(Paragraph(
        f"<i>Document généré le {datetime.now().strftime('%d/%m/%Y')}</i>",
        ParagraphStyle(
            name='Footer',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.gray,
            alignment=TA_CENTER
        )
    ))
    
    doc.build(elements)
    return pdf_path


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
@click.option(
    '--status', '-s',
    type=click.Choice(['paid', 'pending', 'in_transit', 'canceled', 'failed', 'all']),
    default='all',
    help='Filtrer par statut (défaut: all = tous les statuts)'
)
@click.option(
    '--debug',
    is_flag=True,
    default=False,
    help='Afficher des informations de débogage'
)
def main(
    payout: Optional[str],
    from_date: Optional[datetime],
    to_date: Optional[datetime],
    output: Optional[str],
    no_invoices: bool,
    api_key: Optional[str],
    status: str,
    debug: bool
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
    payout_folders = []  # Track folder names for complete ZIP
    
    try:
        if payout:
            # Single payout mode
            zip_path = export_payout(payout, client, output_dir, download_invoices)
            exported_files.append(zip_path)
            # Extract folder name from zip path
            folder_name = os.path.basename(zip_path).replace('.zip', '')
            payout_folders.append(folder_name)
        else:
            # Date range mode
            status_filter = None if status == 'all' else status
            status_display = "tous statuts" if status == 'all' else f"statut={status}"
            
            click.echo(f"\n📅 Recherche des payouts du {from_date.strftime('%d/%m/%Y')} au {to_date.strftime('%d/%m/%Y')} ({status_display})...")
            
            if debug:
                click.echo(f"   🔍 DEBUG: from_date timestamp = {int(from_date.timestamp())}")
                to_date_end = to_date.replace(hour=23, minute=59, second=59)
                click.echo(f"   🔍 DEBUG: to_date timestamp = {int(to_date_end.timestamp())}")
                click.echo(f"   🔍 DEBUG: status_filter = {status_filter}")
            
            payouts = list(client.list_payouts(from_date, to_date, status=status_filter))
            
            if debug and payouts:
                click.echo(f"   🔍 DEBUG: Payouts trouvés:")
                for p in payouts:
                    p_date = timestamp_to_datetime(p.created)
                    click.echo(f"      - {p.id}: {p_date.strftime('%d/%m/%Y')} | status={p.status} | amount={p.amount/100} {p.currency.upper()}")
            
            if not payouts:
                click.echo("ℹ️  Aucun payout trouvé pour cette période.")
                if debug:
                    # Try to fetch recent payouts for debugging
                    click.echo("\n   🔍 DEBUG: Recherche des derniers payouts (sans filtre de date)...")
                    recent_payouts = []
                    for i, p in enumerate(client.list_payouts()):
                        if i >= 5:
                            break
                        recent_payouts.append(p)
                    if recent_payouts:
                        click.echo(f"   🔍 DEBUG: {len(recent_payouts)} payout(s) récent(s) trouvé(s):")
                        for p in recent_payouts:
                            p_date = timestamp_to_datetime(p.created)
                            click.echo(f"      - {p.id}: {p_date.strftime('%d/%m/%Y %H:%M')} | status={p.status}")
                    else:
                        click.echo("   🔍 DEBUG: Aucun payout trouvé sur ce compte Stripe.")
                sys.exit(0)
            
            click.echo(f"✓ {len(payouts)} payout(s) trouvé(s)")
            
            for p in payouts:
                try:
                    zip_path = export_payout(p.id, client, output_dir, download_invoices)
                    exported_files.append(zip_path)
                    # Extract folder name from zip path
                    folder_name = os.path.basename(zip_path).replace('.zip', '')
                    payout_folders.append(folder_name)
                except Exception as e:
                    click.echo(f"❌ Erreur pour {p.id}: {e}", err=True)
                    continue
        
        # Generate guide for Stripe billing invoices
        click.echo("\n📄 Génération du guide pour les factures Stripe...")
        generate_stripe_invoices_guide(output_dir)
        
        # Create complete export ZIP
        if payout_folders:
            click.echo("\n🗜️  Création de l'archive complète pour le comptable...")
            complete_zip = create_complete_export_zip(output_dir, payout_folders)
            click.echo(f"✅ Archive complète créée: {complete_zip}")
        
        # Summary
        click.echo(f"\n{'='*60}")
        click.echo("RÉCAPITULATIF")
        click.echo('='*60)
        click.echo(f"✅ {len(exported_files)} export(s) individuel(s) créé(s):")
        for f in exported_files:
            click.echo(f"   • {f}")
        click.echo("\n📁 Dossier factures_stripe/ créé pour les factures mensuelles Stripe")
        if payout_folders:
            click.echo("\n📦 Archive complète pour le comptable:")
            click.echo(f"   • {os.path.join(output_dir, 'export_comptable_complet.zip')}")
        
    except Exception as e:
        click.echo(f"\n❌ Erreur fatale: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    main()

