"""
PDF Exporter for Stripe payout data - French accounting report
"""

import os
from datetime import datetime
from decimal import Decimal
from typing import List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from ..models import PayoutExportData, TransactionRecord, PayoutSummary
from ..utils import format_date_fr, format_currency_fr, get_stripe_dashboard_url


class PDFExporter:
    """Export payout data to PDF report with French formatting."""
    
    # Colors
    PRIMARY_COLOR = colors.HexColor("#1F4E79")
    SECONDARY_COLOR = colors.HexColor("#2E75B6")
    LIGHT_GRAY = colors.HexColor("#F2F2F2")
    
    def __init__(self, output_dir: str):
        """
        Initialize PDF exporter.
        
        Args:
            output_dir: Directory to save PDF files
        """
        self.output_dir = output_dir
        self.account_id = None  # Will be set when export() is called
        os.makedirs(output_dir, exist_ok=True)
        self._setup_styles()
    
    def _setup_styles(self):
        """Setup paragraph styles for the PDF."""
        self.styles = getSampleStyleSheet()
        
        # Title style
        self.styles.add(ParagraphStyle(
            name='ReportTitle',
            parent=self.styles['Heading1'],
            fontSize=18,
            textColor=self.PRIMARY_COLOR,
            alignment=TA_CENTER,
            spaceAfter=20,
            spaceBefore=10
        ))
        
        # Section header style
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=self.PRIMARY_COLOR,
            spaceBefore=15,
            spaceAfter=10
        ))
        
        # Subsection header style
        self.styles.add(ParagraphStyle(
            name='SubsectionHeader',
            parent=self.styles['Heading3'],
            fontSize=12,
            textColor=self.SECONDARY_COLOR,
            spaceBefore=10,
            spaceAfter=5
        ))
        
        # Normal text style
        self.styles.add(ParagraphStyle(
            name='NormalText',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceBefore=3,
            spaceAfter=3
        ))
        
        # Footer style
        self.styles.add(ParagraphStyle(
            name='Footer',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.gray,
            alignment=TA_CENTER
        ))
        
        # Link style for clickable references
        self.styles.add(ParagraphStyle(
            name='TableLink',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=self.SECONDARY_COLOR,
        ))
    
    def _format_amount(self, amount: Decimal, currency: str) -> str:
        """Format amount with currency for display."""
        return format_currency_fr(int(amount * 100), currency)
    
    def _create_header(self, payout_id: str) -> List:
        """Create the report header."""
        elements = []
        
        # Title
        elements.append(Paragraph(
            "RAPPORT COMPTABLE",
            self.styles['ReportTitle']
        ))
        
        # Subtitle with payout ID (clickable link)
        payout_url = get_stripe_dashboard_url(payout_id, self.account_id)
        if payout_url:
            payout_link = f'Virement Stripe: <a href="{payout_url}" color="#2E75B6"><u>{payout_id}</u></a>'
        else:
            payout_link = f"Virement Stripe: {payout_id}"
        
        elements.append(Paragraph(
            payout_link,
            self.styles['SubsectionHeader']
        ))
        
        # Generation date
        elements.append(Paragraph(
            f"Généré le {format_date_fr(datetime.now(), include_time=True)}",
            self.styles['NormalText']
        ))
        
        elements.append(Spacer(1, 10))
        elements.append(HRFlowable(
            width="100%",
            thickness=1,
            color=self.PRIMARY_COLOR,
            spaceBefore=5,
            spaceAfter=15
        ))
        
        return elements
    
    def _create_summary_section(self, summary: PayoutSummary) -> List:
        """Create the summary section of the report."""
        elements = []
        
        elements.append(Paragraph(
            "1. INFORMATIONS DU VIREMENT",
            self.styles['SectionHeader']
        ))
        
        # Create clickable payout ID
        payout_url = get_stripe_dashboard_url(summary.payout_id, self.account_id)
        if payout_url:
            payout_id_cell = Paragraph(
                f'<a href="{payout_url}" color="#2E75B6"><u>{summary.payout_id}</u></a>',
                self.styles['NormalText']
            )
        else:
            payout_id_cell = summary.payout_id
        
        # Payout info table
        info_data = [
            ["ID Payout", payout_id_cell],
            ["Date de création", format_date_fr(summary.date)],
            ["Date d'arrivée", format_date_fr(summary.date_arrivee)],
            ["Montant", self._format_amount(summary.montant, summary.devise)],
            ["Statut", summary.statut],
            ["Méthode", summary.methode],
            ["Compte bancaire", summary.banque],
        ]
        
        info_table = Table(info_data, colWidths=[5*cm, 10*cm])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), self.PRIMARY_COLOR),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BACKGROUND', (0, 0), (-1, -1), self.LIGHT_GRAY),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.white),
        ]))
        
        elements.append(info_table)
        elements.append(Spacer(1, 15))
        
        return elements
    
    def _format_signed_amount(self, amount: Decimal, currency: str, is_positive: bool) -> str:
        """Format amount with explicit +/- sign for clarity."""
        formatted = format_currency_fr(int(abs(amount) * 100), currency)
        if is_positive:
            return f"+{formatted}"
        else:
            return f"-{formatted}"
    
    def _create_financial_section(self, summary: PayoutSummary) -> List:
        """Create the financial breakdown section with clear +/- signs."""
        elements = []
        
        elements.append(Paragraph(
            "2. DÉTAIL FINANCIER",
            self.styles['SectionHeader']
        ))
        
        # Build financial data with signed amounts for clarity
        financial_data = [
            ["Catégorie", "Montant"],
        ]
        
        # Payments are positive (credits)
        if summary.total_paiements > 0:
            financial_data.append([
                "Total Paiements",
                self._format_signed_amount(summary.total_paiements, summary.devise, True),
            ])
        
        # Refunds are negative (debits)
        if summary.total_remboursements > 0:
            financial_data.append([
                "Total Remboursements",
                self._format_signed_amount(summary.total_remboursements, summary.devise, False),
            ])
        
        # Fees are negative (debits)
        if summary.total_frais > 0:
            financial_data.append([
                "Total Frais Stripe",
                self._format_signed_amount(summary.total_frais, summary.devise, False),
            ])
        
        # Disputes are negative (debits)
        if summary.total_litiges > 0:
            financial_data.append([
                "Total Litiges",
                self._format_signed_amount(summary.total_litiges, summary.devise, False),
            ])
        
        # Payment failures are negative (debits) - shown as separate line
        if summary.total_echecs_paiement > 0:
            financial_data.append([
                "Tentatives de paiement échouées",
                self._format_signed_amount(summary.total_echecs_paiement, summary.devise, False),
            ])
        
        # Other amounts (can be positive or negative)
        if summary.total_autres != 0:
            is_positive = summary.total_autres > 0
            financial_data.append([
                "Total Autres",
                self._format_signed_amount(abs(summary.total_autres), summary.devise, is_positive),
            ])
        
        # Add separator and total
        financial_data.append(["", ""])
        financial_data.append([
            "MONTANT NET VIRÉ",
            self._format_amount(summary.montant, summary.devise),
        ])
        
        financial_table = Table(financial_data, colWidths=[9*cm, 6*cm])
        
        # Calculate row indices for styling
        total_row = len(financial_data) - 1
        separator_row = len(financial_data) - 2
        
        financial_table.setStyle(TableStyle([
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), self.PRIMARY_COLOR),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            
            # Data rows
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica'),
            ('FONTNAME', (1, 1), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
            
            # Total row
            ('FONTNAME', (0, total_row), (-1, total_row), 'Helvetica-Bold'),
            ('BACKGROUND', (0, total_row), (-1, total_row), self.LIGHT_GRAY),
            
            # Grid (exclude separator row)
            ('GRID', (0, 0), (-1, separator_row - 1), 0.5, colors.gray),
            ('LINEABOVE', (0, total_row), (-1, total_row), 1, self.PRIMARY_COLOR),
            ('LINEBELOW', (0, total_row), (-1, total_row), 1, self.PRIMARY_COLOR),
            
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        elements.append(financial_table)
        elements.append(Spacer(1, 15))
        
        return elements
    
    def _create_statistics_section(self, summary: PayoutSummary) -> List:
        """Create the statistics section."""
        elements = []
        
        elements.append(Paragraph(
            "3. STATISTIQUES",
            self.styles['SectionHeader']
        ))
        
        stats_data = [
            ["Indicateur", "Valeur"],
            ["Nombre de transactions", str(summary.nb_transactions)],
            ["Nombre de factures", str(summary.nb_factures)],
            ["Nombre de remboursements", str(summary.nb_remboursements)],
            ["Nombre de litiges", str(summary.nb_litiges)],
        ]
        
        stats_table = Table(stats_data, colWidths=[8*cm, 5*cm])
        stats_table.setStyle(TableStyle([
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), self.PRIMARY_COLOR),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            
            # Data
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (1, 1), (1, -1), 'CENTER'),
            
            ('GRID', (0, 0), (-1, -1), 0.5, colors.gray),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, self.LIGHT_GRAY]),
        ]))
        
        elements.append(stats_table)
        elements.append(Spacer(1, 15))
        
        return elements
    
    def _create_reference_link(self, reference: str, source_id: str = None) -> Paragraph:
        """
        Create a clickable reference link to Stripe dashboard.
        
        Args:
            reference: The Stripe reference ID (txn_xxx) for display
            source_id: The source object ID (ch_, pi_, re_, etc.) for the actual link
            
        Returns:
            Paragraph with clickable link or plain text if no URL available
        """
        display_ref = reference[:35] + "..." if len(reference) > 35 else reference
        
        # Use source_id for the URL (since txn_ IDs don't have dashboard pages)
        # Fall back to reference if source_id is not available
        link_id = source_id or reference
        url = get_stripe_dashboard_url(link_id, self.account_id)
        
        if url:
            # Create clickable link with underline
            link_text = f'<a href="{url}" color="#2E75B6"><u>{display_ref}</u></a>'
            return Paragraph(link_text, self.styles['TableLink'])
        else:
            return Paragraph(display_ref, self.styles['TableLink'])
    
    def _create_transactions_section(self, transactions: List[TransactionRecord]) -> List:
        """Create the transactions detail section."""
        elements = []
        
        elements.append(Paragraph(
            "4. DÉTAIL DES TRANSACTIONS",
            self.styles['SectionHeader']
        ))
        
        if not transactions:
            elements.append(Paragraph(
                "Aucune transaction à afficher.",
                self.styles['NormalText']
            ))
            return elements
        
        # Table header
        header = ["Date", "Réf.", "Type", "Montant Brut", "Frais", "Montant Net"]
        
        # Prepare data rows (limit to first 50 for PDF readability)
        data_rows = [header]
        displayed_transactions = transactions[:50]
        
        for tx in displayed_transactions:
            row = [
                format_date_fr(tx.date),
                self._create_reference_link(tx.reference, tx.source_id),
                tx.type[:15] if tx.type else "",
                self._format_amount(tx.montant_brut, tx.devise),
                self._format_amount(tx.frais, tx.devise),
                self._format_amount(tx.montant_net, tx.devise),
            ]
            data_rows.append(row)
        
        # Create table - column widths: Date=2.2cm, Réf=5cm, Type=2.3cm, Brut=2.5cm, Frais=2cm, Net=3cm (total=17cm)
        tx_table = Table(data_rows, colWidths=[2*cm, 6*cm, 2.75*cm, 2.1*cm, 2.1*cm, 2.1*cm])
        tx_table.setStyle(TableStyle([
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), self.PRIMARY_COLOR),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            
            # Data
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ALIGN', (3, 1), (5, -1), 'RIGHT'),
            
            ('GRID', (0, 0), (-1, -1), 0.5, colors.gray),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, self.LIGHT_GRAY]),
        ]))
        
        elements.append(tx_table)
        
        if len(transactions) > 50:
            elements.append(Spacer(1, 5))
            elements.append(Paragraph(
                f"... et {len(transactions) - 50} autres transactions (voir fichier Excel pour le détail complet)",
                self.styles['NormalText']
            ))
        
        elements.append(Spacer(1, 15))
        
        return elements
    
    def _create_footer(self) -> List:
        """Create the report footer."""
        elements = []
        
        elements.append(HRFlowable(
            width="100%",
            thickness=0.5,
            color=colors.gray,
            spaceBefore=20,
            spaceAfter=10
        ))
        
        elements.append(Paragraph(
            "Ce document est généré automatiquement à partir des données Stripe. "
            "Il est fourni à titre informatif pour justification comptable. "
            "Les fichiers CSV et Excel joints contiennent le détail complet des transactions.",
            self.styles['Footer']
        ))
        
        elements.append(Spacer(1, 5))
        
        elements.append(Paragraph(
            f"Document généré le {format_date_fr(datetime.now(), include_time=True)} - "
            "Stripe Comptable Export v1.0",
            self.styles['Footer']
        ))
        
        return elements
    
    def export(self, data: PayoutExportData, filename: str = "rapport_comptable.pdf") -> str:
        """
        Export payout data to PDF report.
        
        Args:
            data: PayoutExportData object
            filename: Output filename
            
        Returns:
            Path to the created file
        """
        # Store account_id for URL generation
        self.account_id = data.account_id
        
        filepath = os.path.join(self.output_dir, filename)
        
        doc = SimpleDocTemplate(
            filepath,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        elements = []
        
        # Build document sections
        elements.extend(self._create_header(data.summary.payout_id))
        elements.extend(self._create_summary_section(data.summary))
        elements.extend(self._create_financial_section(data.summary))
        elements.extend(self._create_statistics_section(data.summary))
        elements.extend(self._create_transactions_section(data.transactions))
        elements.extend(self._create_footer())
        
        doc.build(elements)
        return filepath

