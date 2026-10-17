"""
ReportLab PDF Generation Service for 80mm Thermal Receipts and A4 Tax Invoices.
Supports custom store logo, GST tax breakup, customer metadata, and reprints.
"""
import io
from datetime import datetime
from typing import Optional, Dict, Any, Union
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    HRFlowable,
)
from services.billing_service import get_bill_details
from services.settings_service import get_shop_settings
from utils.currency import format_rupees, paise_to_rupees_decimal


def generate_bill_pdf(
    bill_id_or_no: Union[int, str],
    paper_size_override: Optional[str] = None,
    db_path: Optional[str] = None
) -> bytes:
    """
    Generate PDF bytes for a given invoice.
    Uses shop_settings.paper_size ('80mm' or 'A4') unless overridden.
    """
    bill = get_bill_details(bill_id_or_no, db_path)
    if not bill:
        raise ValueError(f"Invoice '{bill_id_or_no}' not found.")

    settings = get_shop_settings(db_path)
    paper_size = paper_size_override or settings.get("paper_size", "80mm")

    if paper_size == "A4":
        return _generate_a4_invoice(bill, settings)
    else:
        return _generate_80mm_receipt(bill, settings)


def _generate_80mm_receipt(bill: Dict[str, Any], settings: Dict[str, Any]) -> bytes:
    """Generate 80mm thermal receipt format."""
    buffer = io.BytesIO()

    # Dynamic height calculation to avoid wasting thermal paper roll
    item_count = len(bill.get("items", []))
    page_width = 80 * mm
    calc_height = max(160 * mm, (120 + (item_count * 9)) * mm)
    page_size = (page_width, calc_height)

    doc = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        leftMargin=3 * mm,
        rightMargin=3 * mm,
        topMargin=4 * mm,
        bottomMargin=4 * mm,
    )

    styles = getSampleStyleSheet()

    # Custom styles for 80mm thermal
    style_center = ParagraphStyle(
        "ThermalCenter",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        alignment=1,
        textColor=colors.black,
    )
    style_shop_name = ParagraphStyle(
        "ThermalShopName",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=14,
        alignment=1,
        textColor=colors.black,
    )
    style_bold = ParagraphStyle(
        "ThermalBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.black,
    )
    style_item = ParagraphStyle(
        "ThermalItem",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.black,
    )
    style_right = ParagraphStyle(
        "ThermalRight",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        alignment=2,
        textColor=colors.black,
    )
    style_right_bold = ParagraphStyle(
        "ThermalRightBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        alignment=2,
        textColor=colors.black,
    )

    elements = []

    # 1. Logo (if available)
    logo_blob = settings.get("logo_blob")
    if logo_blob:
        try:
            logo_stream = io.BytesIO(logo_blob)
            img = Image(logo_stream, width=28 * mm, height=18 * mm)
            img.hAlign = "CENTER"
            elements.append(img)
            elements.append(Spacer(1, 2 * mm))
        except Exception:
            pass  # Fall back gracefully if image format fails

    # 2. Store Header
    elements.append(Paragraph(settings.get("shop_name", "Retail Store"), style_shop_name))
    if settings.get("address"):
        elements.append(Paragraph(settings["address"], style_center))
    if settings.get("phone"):
        elements.append(Paragraph(f"Ph: {settings['phone']}", style_center))
    if settings.get("gstin"):
        elements.append(Paragraph(f"GSTIN: {settings['gstin']}", style_center))

    elements.append(Spacer(1, 2 * mm))
    elements.append(HRFlowable(width="100%", thickness=0.8, color=colors.black, spaceAfter=2 * mm))

    # 3. Bill Meta Info
    bill_date_str = bill.get("bill_date", "")
    try:
        dt = datetime.strptime(bill_date_str[:19], "%Y-%m-%d %H:%M:%S")
        formatted_date = dt.strftime("%d-%m-%Y %I:%M %p")
    except Exception:
        formatted_date = bill_date_str

    meta_data = [
        [Paragraph(f"<b>Bill No:</b> {bill['bill_no']}", style_bold),
         Paragraph(f"<b>Mode:</b> {bill['payment_mode'].upper()}", style_right_bold)],
        [Paragraph(f"<b>Date:</b> {formatted_date}", style_item),
         Paragraph(f"<b>Cust:</b> {bill.get('customer_name') or 'Walk-in'}", style_right)]
    ]
    meta_table = Table(meta_data, colWidths=[40 * mm, 34 * mm])
    meta_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 0),
    ]))
    elements.append(meta_table)

    elements.append(HRFlowable(width="100%", thickness=0.8, color=colors.black, spaceBefore=2 * mm, spaceAfter=2 * mm))

    # 4. Itemized Table
    # Columns: Item Name (34mm), Qty (12mm), Rate (12mm), Total (16mm) = 74mm
    table_data = [
        [
            Paragraph("<b>Item</b>", style_bold),
            Paragraph("<b>Qty</b>", style_bold),
            Paragraph("<b>Rate</b>", style_right_bold),
            Paragraph("<b>Total</b>", style_right_bold)
        ]
    ]

    for item in bill.get("items", []):
        rate_rs = paise_to_rupees_decimal(item["unit_price_paise_snapshot"])
        tot_rs = paise_to_rupees_decimal(item["total_paise"])
        table_data.append([
            Paragraph(item["product_name_snapshot"], style_item),
            Paragraph(f"{item['quantity']:g}", style_item),
            Paragraph(f"{rate_rs:.2f}", style_right),
            Paragraph(f"{tot_rs:.2f}", style_right),
        ])

    items_table = Table(table_data, colWidths=[34 * mm, 12 * mm, 12 * mm, 16 * mm])
    items_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 1 * mm),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    elements.append(items_table)

    elements.append(HRFlowable(width="100%", thickness=0.8, color=colors.black, spaceBefore=2 * mm, spaceAfter=2 * mm))

    # 5. Financial Summary
    subtotal_rs = paise_to_rupees_decimal(bill["subtotal_paise"])
    gst_rs = paise_to_rupees_decimal(bill["gst_total_paise"])
    disc_rs = paise_to_rupees_decimal(bill.get("discount_paise", 0))
    grand_rs = paise_to_rupees_decimal(bill["grand_total_paise"])

    sum_rows = [
        [Paragraph("Taxable Base:", style_bold), Paragraph(f"Rs. {subtotal_rs:.2f}", style_right)],
        [Paragraph("Total GST:", style_bold), Paragraph(f"Rs. {gst_rs:.2f}", style_right)],
    ]
    if bill.get("discount_paise", 0) > 0:
        sum_rows.append([Paragraph("Discount:", style_bold), Paragraph(f"-Rs. {disc_rs:.2f}", style_right)])

    sum_rows.append([Paragraph("<b>GRAND TOTAL:</b>", style_bold), Paragraph(f"<b>Rs. {grand_rs:.2f}</b>", style_right_bold)])

    sum_table = Table(sum_rows, colWidths=[42 * mm, 32 * mm])
    sum_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 1 * mm),
        ("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.black),
    ]))
    elements.append(sum_table)

    # 6. Bill Footer Note
    elements.append(Spacer(1, 4 * mm))
    footer_text = settings.get("bill_footer", "Thank you! Visit again.")
    elements.append(Paragraph(footer_text, style_center))
    elements.append(Spacer(1, 1 * mm))
    elements.append(Paragraph("*** Have a Nice Day ***", style_center))

    doc.build(elements)
    return buffer.getvalue()


def _generate_a4_invoice(bill: Dict[str, Any], settings: Dict[str, Any]) -> bytes:
    """Generate professional full-page A4 Tax Invoice format."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )

    styles = getSampleStyleSheet()

    style_title = ParagraphStyle(
        "A4Title",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#1E293B"),
    )
    style_shop_meta = ParagraphStyle(
        "A4ShopMeta",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155"),
    )
    style_heading = ParagraphStyle(
        "A4Heading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        alignment=2,
        textColor=colors.HexColor("#2563EB"),
    )
    style_table_header = ParagraphStyle(
        "A4TH",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=colors.white,
        alignment=1,
    )
    style_cell = ParagraphStyle(
        "A4Cell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#0F172A"),
    )
    style_cell_center = ParagraphStyle(
        "A4CellC",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        alignment=1,
        textColor=colors.HexColor("#0F172A"),
    )
    style_cell_right = ParagraphStyle(
        "A4CellR",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        alignment=2,
        textColor=colors.HexColor("#0F172A"),
    )
    style_cell_right_bold = ParagraphStyle(
        "A4CellRB",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        alignment=2,
        textColor=colors.HexColor("#0F172A"),
    )

    elements = []

    # 1. Header Grid: Store info on left, Invoice title & meta on right
    logo_blob = settings.get("logo_blob")
    logo_img = None
    if logo_blob:
        try:
            logo_img = Image(io.BytesIO(logo_blob), width=35 * mm, height=22 * mm)
            logo_img.hAlign = "LEFT"
        except Exception:
            pass

    bill_date_str = bill.get("bill_date", "")
    try:
        dt = datetime.strptime(bill_date_str[:19], "%Y-%m-%d %H:%M:%S")
        formatted_date = dt.strftime("%d-%m-%Y %I:%M %p")
    except Exception:
        formatted_date = bill_date_str

    left_content = []
    if logo_img:
        left_content.append(logo_img)
    left_content.append(Paragraph(f"<b>{settings.get('shop_name', 'Store Name')}</b>", style_title))
    if settings.get("address"):
        left_content.append(Paragraph(settings["address"], style_shop_meta))
    if settings.get("phone"):
        left_content.append(Paragraph(f"Phone: {settings['phone']}", style_shop_meta))
    if settings.get("gstin"):
        left_content.append(Paragraph(f"<b>GSTIN:</b> {settings['gstin']}", style_shop_meta))

    right_content = [
        Paragraph("TAX INVOICE", style_heading),
        Spacer(1, 2 * mm),
        Paragraph(f"<b>Invoice No:</b> {bill['bill_no']}", style_cell_right),
        Paragraph(f"<b>Invoice Date:</b> {formatted_date}", style_cell_right),
        Paragraph(f"<b>Payment Mode:</b> {bill['payment_mode'].upper()}", style_cell_right),
        Paragraph(f"<b>Status:</b> {bill['status'].upper()}", style_cell_right),
    ]

    header_table = Table([[left_content, right_content]], colWidths=[105 * mm, 81 * mm])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 4 * mm))

    # 2. Bill To (Customer Details) Banner
    cust_name = bill.get("customer_name") or "Walk-in Retail Customer"
    cust_phone = bill.get("customer_phone") or "N/A"
    cust_box = [
        [
            Paragraph(f"<b>Billed To:</b> {cust_name}", style_cell),
            Paragraph(f"<b>Contact:</b> {cust_phone}", style_cell_right)
        ]
    ]
    cust_table = Table(cust_box, colWidths=[110 * mm, 76 * mm])
    cust_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
        ("PADDING", (0, 0), (-1, -1), 2.5 * mm),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
    ]))
    elements.append(cust_table)
    elements.append(Spacer(1, 4 * mm))

    # 3. Item Table
    # Columns: S.No (10mm), Item Description (60mm), Unit (16mm), Qty (16mm), Rate (24mm), GST% (18mm), Tax (20mm), Total (22mm) = 186mm
    items_header = [
        Paragraph("<b>#</b>", style_table_header),
        Paragraph("<b>Item Description</b>", style_table_header),
        Paragraph("<b>Unit</b>", style_table_header),
        Paragraph("<b>Qty</b>", style_table_header),
        Paragraph("<b>Rate (Rs.)</b>", style_table_header),
        Paragraph("<b>GST</b>", style_table_header),
        Paragraph("<b>Tax (Rs.)</b>", style_table_header),
        Paragraph("<b>Total (Rs.)</b>", style_table_header),
    ]
    item_rows = [items_header]

    for idx, item in enumerate(bill.get("items", []), start=1):
        rate_rs = paise_to_rupees_decimal(item["unit_price_paise_snapshot"])
        tax_rs = paise_to_rupees_decimal(item["gst_amount_paise"])
        tot_rs = paise_to_rupees_decimal(item["total_paise"])

        item_rows.append([
            Paragraph(str(idx), style_cell_center),
            Paragraph(item["product_name_snapshot"], style_cell),
            Paragraph(item.get("unit", "pcs"), style_cell_center),
            Paragraph(f"{item['quantity']:g}", style_cell_center),
            Paragraph(f"{rate_rs:.2f}", style_cell_right),
            Paragraph(f"{item['gst_rate_snapshot']}%", style_cell_center),
            Paragraph(f"{tax_rs:.2f}", style_cell_right),
            Paragraph(f"{tot_rs:.2f}", style_cell_right),
        ])

    table_style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563EB")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("PADDING", (0, 0), (-1, -1), 2 * mm),
    ])

    items_doc_table = Table(
        item_rows,
        colWidths=[10 * mm, 60 * mm, 16 * mm, 16 * mm, 24 * mm, 18 * mm, 20 * mm, 22 * mm]
    )
    items_doc_table.setStyle(table_style)
    elements.append(items_doc_table)
    elements.append(Spacer(1, 4 * mm))

    # 4. GST Breakdown & Grand Total Row
    subtotal_rs = paise_to_rupees_decimal(bill["subtotal_paise"])
    gst_rs = paise_to_rupees_decimal(bill["gst_total_paise"])
    disc_rs = paise_to_rupees_decimal(bill.get("discount_paise", 0))
    grand_rs = paise_to_rupees_decimal(bill["grand_total_paise"])

    half_gst = gst_rs / 2

    # Left: GST Slabs Note, Right: Totals
    left_gst_note = [
        Paragraph("<b>Tax Breakdown:</b>", style_cell),
        Paragraph(f"• CGST (Central Tax): Rs. {half_gst:.2f}", style_shop_meta),
        Paragraph(f"• SGST (State Tax): Rs. {half_gst:.2f}", style_shop_meta),
        Spacer(1, 3 * mm),
        Paragraph(f"<i>{settings.get('bill_footer', 'Thank you! Visit again.')}</i>", style_shop_meta)
    ]

    totals_box = [
        [Paragraph("Taxable Value:", style_cell), Paragraph(f"Rs. {subtotal_rs:.2f}", style_cell_right)],
        [Paragraph("Total GST Tax:", style_cell), Paragraph(f"Rs. {gst_rs:.2f}", style_cell_right)],
    ]
    if bill.get("discount_paise", 0) > 0:
        totals_box.append([Paragraph("Discount:", style_cell), Paragraph(f"-Rs. {disc_rs:.2f}", style_cell_right)])

    totals_box.append([
        Paragraph("<b>GRAND TOTAL:</b>", style_cell),
        Paragraph(f"<b>Rs. {grand_rs:.2f}</b>", style_cell_right_bold)
    ])

    totals_table = Table(totals_box, colWidths=[40 * mm, 46 * mm])
    totals_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E2E8F0")),
        ("PADDING", (0, 0), (-1, -1), 2 * mm),
    ]))

    summary_grid = Table([[left_gst_note, totals_table]], colWidths=[100 * mm, 86 * mm])
    summary_grid.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    elements.append(summary_grid)

    elements.append(Spacer(1, 10 * mm))
    sign_box = Table(
        [[Paragraph("Authorized Signatory / Cashier", style_cell_right)]],
        colWidths=[186 * mm]
    )
    elements.append(sign_box)

    doc.build(elements)
    return buffer.getvalue()
