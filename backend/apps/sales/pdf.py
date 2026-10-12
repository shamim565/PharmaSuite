"""Invoice PDF rendering (reportlab)."""

from decimal import Decimal
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.common.settings_service import get_setting_value


def _money(value) -> str:
    return f"{Decimal(value or 0):,.2f}"


def _date(value) -> str:
    return value.strftime("%d %b %Y") if value else "—"


def _company_line() -> str:
    parts = [
        get_setting_value("COMPANY_ADDRESS", default="") or "",
        get_setting_value("COMPANY_PHONE", default="") or "",
        f"BIN: {get_setting_value('COMPANY_BIN', default='')}" if get_setting_value("COMPANY_BIN") else "",
        f"VAT: {get_setting_value('COMPANY_VAT_REG', default='')}"
        if get_setting_value("COMPANY_VAT_REG")
        else "",
    ]
    return " · ".join(part for part in parts if part)


def build_invoice_pdf(invoice, *, include_cost: bool = False) -> bytes:
    import apps.sales.models as _models  # noqa: F401  (ensures app loaded)

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=f"Invoice {invoice.number or invoice.id}",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "InvoiceTitle", parent=styles["Title"], fontSize=16, spaceAfter=2
    )
    small = ParagraphStyle("Small", parent=styles["BodyText"], fontSize=8, textColor=colors.grey)
    body = styles["BodyText"]

    company_name = get_setting_value("COMPANY_NAME", default="") or "PharmaSuite"
    elements = [
        Paragraph(company_name, title_style),
        Paragraph(_company_line(), small),
        Spacer(1, 6),
        Paragraph("<b>SALES INVOICE</b>", body),
        Spacer(1, 4),
    ]

    meta_rows = [
        ["Invoice", invoice.number or "DRAFT"],
        ["Date", _date(invoice.business_date)],
        ["Due date", _date(invoice.due_date)],
        ["Status", f"{invoice.lifecycle} / {invoice.payment_status}"],
        ["Branch", f"{invoice.branch.name} {invoice.branch.phone or ''}".strip()],
    ]
    if invoice.doctor_id:
        meta_rows.append(["Doctor", str(invoice.doctor.name) if invoice.doctor else "—"])
    if invoice.sales_rep_id:
        meta_rows.append(["Sales rep", str(invoice.sales_rep.name) if invoice.sales_rep else "—"])
    if invoice.confirmed_at:
        confirmed_by = invoice.confirmed_by.full_name if invoice.confirmed_by else "—"
        meta_rows.append(
            ["Confirmed", f"{confirmed_by} · {invoice.confirmed_at:%d %b %Y %H:%M}"]
        )

    customer_rows = [
        ["Customer", f"{invoice.customer.name} ({invoice.customer.code})"],
        ["Phone", invoice.customer.phone or "—"],
        ["Address", invoice.customer.address or "—"],
    ]

    meta_table = Table(
        [[Paragraph(f"<b>{label}</b>", small), Paragraph(str(value), small)] for label, value in meta_rows],
        colWidths=[22 * mm, 65 * mm],
    )
    customer_table = Table(
        [[Paragraph(f"<b>{label}</b>", small), Paragraph(str(value), small)] for label, value in customer_rows],
        colWidths=[22 * mm, 65 * mm],
    )
    header_table = Table([[customer_table, meta_table]], colWidths=[92 * mm, 88 * mm])
    header_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    elements.append(header_table)
    elements.append(Spacer(1, 8))

    header = ["#", "Item", "Batch", "Qty", "Rate", "Disc", "VAT", "Amount"]
    if include_cost:
        header.insert(6, "Cost")
    rows = [header]
    for item in invoice.items.select_related("medicine", "batch").order_by("line_no"):
        row = [
            str(item.line_no),
            f"{item.medicine.name} ({item.medicine.code}){' [FREE]' if item.is_free_goods else ''}",
            item.batch_number or "—",
            _money(item.qty),
            _money(item.unit_price),
            _money(item.line_discount),
            _money(item.vat_amount),
            _money(item.line_total),
        ]
        if include_cost:
            row.insert(6, _money(item.unit_cost))
        rows.append(row)

    col_widths = [8 * mm, 55 * mm, 22 * mm, 16 * mm, 18 * mm, 16 * mm, 16 * mm, 20 * mm]
    if include_cost:
        col_widths.insert(6, 18 * mm)
    items_table = Table(rows, colWidths=col_widths, repeatRows=1)
    items_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    elements.append(items_table)
    elements.append(Spacer(1, 8))

    totals = [
        ["Subtotal", _money(invoice.subtotal)],
        ["Discount", _money(invoice.discount_total)],
        ["VAT", _money(invoice.vat_total)],
        ["Round off", _money(invoice.round_off)],
        ["Grand total", _money(invoice.grand_total)],
        ["Paid", _money(invoice.paid_total)],
        ["Outstanding", _money(invoice.outstanding)],
    ]
    totals_table = Table(
        [[Paragraph(f"<b>{label}</b>", small), Paragraph(value, small)] for label, value in totals],
        colWidths=[30 * mm, 30 * mm],
        hAlign="RIGHT",
    )
    totals_table.setStyle(
        TableStyle([("ALIGN", (1, 0), (1, -1), "RIGHT"), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)])
    )
    elements.append(totals_table)

    if invoice.notes:
        elements.append(Spacer(1, 8))
        elements.append(Paragraph(f"Notes: {invoice.notes}", small))
    elements.append(Spacer(1, 10))
    elements.append(
        Paragraph("Generated by PharmaSuite", small)
    )

    document.build(elements)
    return buffer.getvalue()
