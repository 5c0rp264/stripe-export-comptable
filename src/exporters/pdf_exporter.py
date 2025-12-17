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
from ..utils import format_date_fr, format_currency_fr


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
        
        # Subtitle with payout ID
        elements.append(Paragraph(
            f"Virement Stripe: {payout_id}",
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
        
        # Payout info table
        info_data = [
            ["ID Payout", summary.payout_id],
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
    
    def _create_financial_section(self, summary: PayoutSummary) -> List:
        """Create the financial breakdown section."""
        elements = []
        
        elements.append(Paragraph(
            "2. DÉTAIL FINANCIER",
            self.styles['SectionHeader']
        ))
        
        # Financial breakdown table
        financial_data = [
            ["Catégorie", "Montant", "Devise"],
            ["Total Paiements", self._format_amount(summary.total_paiements, summary.devise), summary.devise],
            ["Total Remboursements", self._format_amount(summary.total_remboursements, summary.devise), summary.devise],
            ["Total Frais Stripe", self._format_amount(summary.total_frais, summary.devise), summary.devise],
            ["Total Litiges", self._format_amount(summary.total_litiges, summary.devise), summary.devise],
            ["Total Autres", self._format_amount(summary.total_autres, summary.devise), summary.devise],
            ["", "", ""],
            ["MONTANT NET VIRÉ", self._format_amount(summary.montant, summary.devise), summary.devise],
        ]
        
        financial_table = Table(financial_data, colWidths=[7*cm, 5*cm, 3*cm])
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
            ('ALIGN', (2, 1), (2, -1), 'CENTER'),
            
            # Total row
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('BACKGROUND', (0, -1), (-1, -1), self.LIGHT_GRAY),
            
            # Grid
            ('GRID', (0, 0), (-1, -2), 0.5, colors.gray),
            ('LINEABOVE', (0, -1), (-1, -1), 1, self.PRIMARY_COLOR),
            ('LINEBELOW', (0, -1), (-1, -1), 1, self.PRIMARY_COLOR),
            
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
                tx.reference[:15] + "..." if len(tx.reference) > 15 else tx.reference,
                tx.type[:15] if tx.type else "",
                self._format_amount(tx.montant_brut, tx.devise),
                self._format_amount(tx.frais, tx.devise),
                self._format_amount(tx.montant_net, tx.devise),
            ]
            data_rows.append(row)
        
        # Create table
        tx_table = Table(data_rows, colWidths=[2.5*cm, 3*cm, 3*cm, 3*cm, 2.5*cm, 3*cm])
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

