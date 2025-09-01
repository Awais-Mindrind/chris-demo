"""PDF generation using ReportLab."""
import os
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, Any, List
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch

from app.db import get_db
from app.models import Quote, Account, Pricebook, Sku, QuoteLine


# =============================================================================
# CPQ VIEWMODEL & HELPERS
# =============================================================================

def fmt_money(amount: Decimal, currency: str) -> str:
    """Format money with thousands separator and two decimals (grayscale-safe)."""
    if amount is None:
        amount = Decimal("0")
    try:
        q = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        q = Decimal("0.00")
    return f"{currency} {q:,.2f}"


@dataclass
class LineDoc:
    index: int
    product_name: str
    sku_code: str
    qty: int
    unit_price: Decimal
    discount_pct: float = 0.0
    line_total: Decimal = Decimal("0")
    indent_level: int = 0
    is_bundle_parent: bool = False
    is_required_option: bool = False
    is_subscription: bool = False
    term_months: Optional[int] = None
    attributes_text: Optional[str] = None


@dataclass
class QuoteDoc:
    quote_id: int
    quote_date: datetime
    valid_until: Optional[datetime]
    term_months: Optional[int]
    pricebook_name: str
    currency: str
    bill_to_name: str
    bill_to_address: str
    ship_to_name: str
    ship_to_address: str
    lines: List[LineDoc] = field(default_factory=list)
    subtotal: Decimal = Decimal("0")
    total_discount_abs: Decimal = Decimal("0")
    total_discount_pct: float = 0.0
    tax: Decimal = Decimal("0")
    grand_total: Decimal = Decimal("0")


def _derive_quote_doc(quote: Quote, account: Account, pricebook: Pricebook) -> QuoteDoc:
    """Derive a CPQ-style QuoteDoc from DB entities without schema changes."""
    currency = getattr(pricebook, "currency", "USD") or "USD"
    bill_name = getattr(account, "name", "Customer Name") or "Customer Name"
    address_placeholder = "Address not provided"
    bill_addr = getattr(account, "address", None) or address_placeholder
    ship_name = bill_name
    ship_addr = bill_addr

    # Load SKUs for hierarchy/attributes if possible
    db = None
    try:
        db = next(get_db())
    except Exception:
        db = None

    sku_map: Dict[int, Sku] = {}
    if db is not None and quote.lines:
        sku_ids = [line.sku_id for line in quote.lines]
        for sku in db.query(Sku).filter(Sku.id.in_(sku_ids)).all():
            sku_map[sku.id] = sku

    # Build parent-child map to identify bundle parents
    parent_child: Dict[int, List[int]] = {}
    for line in quote.lines:
        sku = sku_map.get(line.sku_id)
        if sku and sku.parent_sku_id:
            parent_child.setdefault(sku.parent_sku_id, []).append(sku.id)

    line_docs: List[LineDoc] = []
    subtotal = Decimal("0")
    undiscounted = Decimal("0")
    for idx, line in enumerate(quote.lines, start=1):
        sku = sku_map.get(line.sku_id)
        sku_code = (sku.code if sku and sku.code else str(line.sku_id))
        product_name = (sku.name if sku and sku.name else f"SKU {line.sku_id}")
        attrs = sku.attributes if (sku and sku.attributes) else {}
        indent_level = 1 if (sku and sku.parent_sku_id) else 0
        is_parent = bool(sku and sku.id in parent_child)
        is_required = bool(attrs.get("is_required_option", False)) if isinstance(attrs, dict) else False
        is_sub = bool(isinstance(attrs, dict) and (attrs.get("is_subscription") or attrs.get("term_months")))
        term_months = int(attrs.get("term_months")) if (isinstance(attrs, dict) and attrs.get("term_months")) else None

        # Attributes inline text
        attributes_text = None
        if isinstance(attrs, dict):
            parts = []
            for k, v in attrs.items():
                if k in {"is_required_option", "is_subscription", "term_months"}:
                    continue
                parts.append(f"{k}: {v}")
            attributes_text = "; ".join(parts) if parts else None

        unit_price = line.unit_price or (Decimal(str(getattr(sku, "unit_price", 0))) if sku else Decimal("0"))
        undiscount_line = (unit_price or Decimal("0")) * line.qty
        discount_pct = float(getattr(line, "discount_pct", 0.0) or 0.0)
        line_total = undiscount_line * Decimal(str(1 - discount_pct))
        undiscounted += undiscount_line
        subtotal += line_total

        line_docs.append(LineDoc(
            index=idx,
            product_name=product_name,
            sku_code=sku_code,
            qty=line.qty,
            unit_price=unit_price or Decimal("0"),
            discount_pct=discount_pct,
            line_total=line_total,
            indent_level=indent_level,
            is_bundle_parent=is_parent,
            is_required_option=is_required,
            is_subscription=is_sub,
            term_months=term_months,
            attributes_text=attributes_text
        ))

    total_discount_abs = undiscounted - subtotal
    total_discount_pct = float((total_discount_abs / undiscounted).quantize(Decimal("0.0001"))) if undiscounted > 0 else 0.0
    tax = Decimal("0")  # No tax calculation; placeholder per scope
    grand_total = subtotal + tax

    return QuoteDoc(
        quote_id=quote.id,
        quote_date=quote.created_at,
        valid_until=None,
        term_months=None,
        pricebook_name=pricebook.name,
        currency=currency,
        bill_to_name=bill_name,
        bill_to_address=bill_addr,
        ship_to_name=ship_name,
        ship_to_address=ship_addr,
        lines=line_docs,
        subtotal=subtotal,
        total_discount_abs=total_discount_abs,
        total_discount_pct=total_discount_pct,
        tax=tax,
        grand_total=grand_total
    )


class QuotePDFGenerator:
    """Generate professional quote PDFs using ReportLab."""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles for the quote."""
        # Company header style
        self.company_style = ParagraphStyle(
            'CompanyHeader',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.black,
            alignment=TA_CENTER,
            spaceAfter=20
        )
        
        # Quote title style
        self.quote_title_style = ParagraphStyle(
            'QuoteTitle',
            parent=self.styles['Heading2'],
            fontSize=18,
            textColor=colors.black,
            alignment=TA_CENTER,
            spaceAfter=15
        )
        
        # Section header style
        self.section_style = ParagraphStyle(
            'SectionHeader',
            parent=self.styles['Heading3'],
            fontSize=14,
            textColor=colors.black,
            spaceAfter=10,
            spaceBefore=15
        )
        
        # Normal text style
        self.normal_style = ParagraphStyle(
            'NormalText',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceAfter=6
        )
        
        # Table header style
        self.table_header_style = ParagraphStyle(
            'TableHeader',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.black,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        # Footer style
        self.footer_style = ParagraphStyle(
            'Footer',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.grey,
            alignment=TA_CENTER
        )
    
    def _create_header(self, company_name: str = "Sales Quoting Engine") -> list:
        """Create the company header section."""
        elements = []
        
        # Company name/logo placeholder
        elements.append(Paragraph(company_name, self.company_style))
        elements.append(Spacer(1, 10))
        
        # Company address placeholder
        company_address = [
            "123 Business Street",
            "Suite 100",
            "City, State 12345",
            "Phone: (555) 123-4567",
            "Email: quotes@company.com"
        ]
        
        for line in company_address:
            elements.append(Paragraph(line, self.normal_style))
        
        elements.append(Spacer(1, 20))
        return elements
    
    def _create_quote_meta_panel(self, doc: "QuoteDoc") -> list:
        """Create compact Quote Meta panel."""
        elements = []
        elements.append(Paragraph("QUOTE SUMMARY", self.quote_title_style))
        data = [
            ["Quote #:", f"Q-{doc.quote_id:04d}", "Quote Date:", doc.quote_date.strftime('%Y-%m-%d')],
            ["Valid Until:", doc.valid_until.strftime('%Y-%m-%d') if doc.valid_until else "—", "Term (months):", str(doc.term_months) if doc.term_months else "—"],
            ["Pricebook:", doc.pricebook_name, "Currency:", doc.currency]
        ]
        t = Table(data, colWidths=[1.2*inch, 2.0*inch, 1.2*inch, 2.0*inch])
        t.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('LINEABOVE', (0, 0), (-1, 0), 0.25, colors.grey),
            ('LINEBELOW', (0, -1), (-1, -1), 0.25, colors.grey),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 6))
        return elements
    
    def _create_bill_ship_section(self, doc: "QuoteDoc") -> list:
        """Create Bill To / Ship To two-column section."""
        elements = []
        elements.append(Paragraph("BILL TO / SHIP TO", self.section_style))
        bill = [Paragraph(doc.bill_to_name, self.normal_style), Paragraph(doc.bill_to_address, self.normal_style)]
        ship = [Paragraph(doc.ship_to_name, self.normal_style), Paragraph(doc.ship_to_address, self.normal_style)]
        t = Table([
            [Paragraph("Bill To", self.table_header_style), Paragraph("Ship To", self.table_header_style)],
            [bill, ship]
        ], colWidths=[3.25*inch, 3.25*inch])
        t.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 10))
        return elements
    
    def _create_line_items_table(self, doc: "QuoteDoc") -> list:
        """Create CPQ-style line items table with bundles/options/subscriptions."""
        elements = []
        elements.append(Paragraph("LINE ITEMS", self.section_style))

        header = [
            Paragraph("#", self.table_header_style),
            Paragraph("Product", self.table_header_style),
            Paragraph("SKU", self.table_header_style),
            Paragraph("Qty", self.table_header_style),
            Paragraph("Unit", self.table_header_style),
            Paragraph("Disc %", self.table_header_style),
            Paragraph("Line Total", self.table_header_style),
        ]

        data: List[List[Any]] = [header]
        for line in doc.lines:
            # Product cell with indentation and attributes/subscription notes
            name_parts = []
            name = line.product_name
            if line.is_bundle_parent:
                name = f"<b>{name}</b> (Bundle)"
            if line.is_required_option:
                name += " <font size=8>(Required)</font>"
            name_parts.append(name)
            if line.attributes_text:
                name_parts.append(f"<font size=8 color=grey>{line.attributes_text}</font>")
            if line.is_subscription and line.term_months:
                per_unit = line.unit_price
                extended_per_unit = per_unit * Decimal(str(line.term_months))
                name_parts.append(
                    f"<font size=8>$ {per_unit:.2f} / month × {line.term_months} months = {extended_per_unit:.2f} per unit</font>"
                )
            product_par = Paragraph("<br/>".join(name_parts), self.normal_style)

            row = [
                str(line.index),
                product_par,
                line.sku_code,
                str(line.qty if line.qty is not None else ""),
                fmt_money(line.unit_price, doc.currency),
                f"{int(line.discount_pct * 100)}%" if line.discount_pct else "—",
                fmt_money(line.line_total, doc.currency)
            ]
            data.append(row)

        col_widths = [0.4*inch, 3.0*inch, 0.9*inch, 0.6*inch, 0.9*inch, 0.7*inch, 1.0*inch]
        t = Table(data, colWidths=col_widths, repeatRows=1)
        style_cmds = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('ALIGN', (3, 1), (3, -1), 'RIGHT'),
            ('ALIGN', (4, 1), (4, -1), 'RIGHT'),
            ('ALIGN', (5, 1), (5, -1), 'RIGHT'),
            ('ALIGN', (6, 1), (6, -1), 'RIGHT'),
            ('VALIGN', (0, 1), (-1, -1), 'TOP'),
        ]
        # Indentation via left padding per row
        for i, line in enumerate(doc.lines, start=1):
            pad = 6 + (line.indent_level * 12)
            style_cmds.append(('LEFTPADDING', (1, i), (1, i), pad))
            if line.is_bundle_parent:
                style_cmds.append(('FONTNAME', (1, i), (1, i), 'Helvetica-Bold'))

        t.setStyle(TableStyle(style_cmds))
        elements.append(t)
        elements.append(Spacer(1, 12))
        return elements
    
    def _create_summary_band(self, doc: "QuoteDoc") -> list:
        """Create right-aligned Pricing Summary band."""
        elements = []
        elements.append(Paragraph("PRICING SUMMARY", self.section_style))
        data = [
            ["Subtotal", fmt_money(doc.subtotal + doc.total_discount_abs, doc.currency)],
            ["Discount", f"{fmt_money(doc.total_discount_abs, doc.currency)} ({int(doc.total_discount_pct*100)}%)"],
            ["Tax", fmt_money(doc.tax, doc.currency)],
            ["Grand Total", fmt_money(doc.grand_total, doc.currency)],
        ]
        t = Table(data, colWidths=[2.5*inch, 2.0*inch])
        t.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -2), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, -2), 'Helvetica'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ('BACKGROUND', (0, -1), (-1, -1), colors.whitesmoke),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 12))
        return elements
    
    def _create_footer(self) -> list:
        """Create the footer section with terms and signature."""
        elements = []
        
        # Terms and conditions
        elements.append(Paragraph("TERMS AND CONDITIONS:", self.section_style))
        terms = [
            "• This quote is valid for 30 days from the date of issue",
            "• Payment terms: Net 30 days",
            "• All prices are subject to change without notice",
            "• Delivery: Standard shipping included",
            "• Returns: 30-day return policy for unused items"
        ]
        
        for term in terms:
            elements.append(Paragraph(term, self.normal_style))
        
        elements.append(Spacer(1, 20))
        
        # Signature section
        signature_data = [
            ["Customer Signature:", "_________________________"],
            ["Date:", "_________________________"],
            ["Authorized By:", "_________________________"]
        ]
        
        signature_table = Table(signature_data, colWidths=[2*inch, 4*inch])
        signature_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey)
        ]))
        
        elements.append(signature_table)
        elements.append(Spacer(1, 20))
        
        # Footer note
        footer_note = "Thank you for your business! For questions about this quote, please contact our sales team."
        elements.append(Paragraph(footer_note, self.footer_style))
        
        return elements
    
    def _create_page_template(self):
        """Create a custom page template with header and footer."""
        def header_footer(canvas, doc):
            # Header
            canvas.saveState()
            canvas.setFont('Helvetica', 9)
            canvas.setFillColor(colors.grey)
            canvas.drawString(inch, doc.height + inch + 0.5*inch, "Sales Quoting Engine - Professional Quote")
            canvas.restoreState()
            
            # Footer
            canvas.saveState()
            canvas.setFont('Helvetica', 8)
            canvas.setFillColor(colors.grey)
            canvas.drawString(inch, 0.5*inch, f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            canvas.drawRightString(doc.width + inch, 0.5*inch, f"Page {doc.page}")
            canvas.restoreState()
        
        return header_footer
    
    def generate_quote_pdf(self, quote_id: int, output_path: str = None) -> str:
        """Generate a complete quote PDF document.
        
        Args:
            quote_id: Quote ID to generate PDF for
            output_path: Optional output path for the PDF
            
        Returns:
            Path to the generated PDF file
        """
        # Get database session
        db = next(get_db())
        
        try:
            # Fetch quote with all related data
            quote = db.query(Quote).filter(Quote.id == quote_id).first()
            if not quote:
                raise ValueError(f"Quote with ID {quote_id} not found")
            
            # Fetch related data
            account = db.query(Account).filter(Account.id == quote.account_id).first()
            pricebook = db.query(Pricebook).filter(Pricebook.id == quote.pricebook_id).first()
            
            if not account or not pricebook:
                raise ValueError("Quote data incomplete - missing account or pricebook")
            
            # Generate output path if not provided
            if output_path is None:
                os.makedirs("public", exist_ok=True)
                output_path = f"public/quote_{quote_id}.pdf"
            
            # Build view model
            qdoc = _derive_quote_doc(quote, account, pricebook)

            # Create PDF document
            doc = SimpleDocTemplate(
                output_path,
                pagesize=letter,
                rightMargin=inch,
                leftMargin=inch,
                topMargin=inch,
                bottomMargin=inch
            )

            # Build PDF content
            story = []
            story.extend(self._create_header())
            story.extend(self._create_quote_meta_panel(qdoc))
            story.extend(self._create_bill_ship_section(qdoc))
            story.extend(self._create_summary_band(qdoc))
            story.extend(self._create_line_items_table(qdoc))
            story.extend(self._create_footer())

            doc.build(story)
            
            return output_path
            
        except Exception as e:
            raise RuntimeError(f"Failed to generate PDF for quote {quote_id}: {str(e)}")
        finally:
            db.close()


def generate_quote_pdf(quote_id: int, output_path: str = None) -> str:
    """Generate a PDF quote document.
    
    Args:
        quote_id: Quote ID (integer)
        output_path: Optional output path for the PDF
        
    Returns:
        Path to the generated PDF file
    """
    generator = QuotePDFGenerator()
    return generator.generate_quote_pdf(quote_id, output_path)


def render_quote_pdf(quote_id: int) -> str:
    """Render quote as PDF and return file path.
    
    Args:
        quote_id: Quote ID to render
        
    Returns:
        Path to the generated PDF file
    """
    return generate_quote_pdf(quote_id)


def get_quote_pdf_url(quote_id: int) -> str:
    """Get the URL for a quote PDF.
    
    Args:
        quote_id: Quote ID
        
    Returns:
        URL path to the PDF file
    """
    pdf_path = render_quote_pdf(quote_id)
    # Convert file path to URL path
    if pdf_path.startswith("public/"):
        return f"/public/{os.path.basename(pdf_path)}"
    return f"/quotes/{quote_id}/pdf"
