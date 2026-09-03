"""Purchase record PDF rendering (reportlab)."""

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


def build_purchase_pdf(purchase) -> bytes:
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=f"Purchase {purchase.number or purchase.id}",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "PurchaseTitle", parent=styles["Title"], fontSize=16, spaceAfter=2
    )
    small = ParagraphStyle("Small", parent=styles["BodyText"], fontSize=8, textColor=colors.grey)
    body = styles["BodyText"]

    company_name = get_setting_value("COMPANY_NAME", default="") or "Medicine Dealer ERP"
    elements = [
        Paragraph(company_name, title_style),
        Paragraph(_company_line(), small),
        Spacer(1, 6),
        Paragraph("<b>PURCHASE RECORD</b>", body),
        Spacer(1, 4),
    ]

    meta_rows = [
        ["Purchase", purchase.number or "DRAFT"],
        ["Business date", _date(purchase.business_date)],
        ["Supplier invoice", purchase.supplier_invoice_number or "—"],
        ["Invoice date", _date(purchase.supplier_invoice_date)],
        ["Status", f"{purchase.lifecycle} / {purchase.payment_status}"],
        ["Branch", f"{purchase.branch.name} {purchase.branch.phone or ''}".strip()],
    ]
    if purchase.confirmed_at:
        confirmed_by = purchase.confirmed_by.full_name if purchase.confirmed_by else "—"
        meta_rows.append(
            ["Confirmed", f"{confirmed_by} · {purchase.confirmed_at:%d %b %Y %H:%M}"]
        )

    supplier_rows = [
        ["Supplier", f"{purchase.supplier.name} ({purchase.supplier.code})"],
        ["Phone", purchase.supplier.phone or "—"],
        ["Address", purchase.supplier.address or "—"],
    ]

    meta_table = Table(
        [[Paragraph(f"<b>{label}</b>", small), Paragraph(str(value), small)] for label, value in meta_rows],
        colWidths=[25 * mm, 62 * mm],
    )
    supplier_table = Table(
        [[Paragraph(f"<b>{label}</b>", small), Paragraph(str(value), small)] for label, value in supplier_rows],
        colWidths=[22 * mm, 65 * mm],
    )
    header_table = Table([[supplier_table, meta_table]], colWidths=[92 * mm, 88 * mm])
    header_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    elements.append(header_table)
    elements.append(Spacer(1, 8))

    header = ["#", "Item", "Batch", "Expiry", "Qty", "Bonus", "Cost", "Disc", "VAT", "Net"]
    rows = [header]
    for item in purchase.items.select_related("medicine", "batch").order_by("line_no"):
        rows.append(
            [
                str(item.line_no),
                f"{item.medicine.name} ({item.medicine.code})",
                item.batch_number or "—",
                _date(item.expiry_date),
                _money(item.qty_base),
                _money(item.bonus_qty_base),
                _money(item.unit_cost),
                _money(item.line_discount),
                _money(item.vat_amount),
                _money(item.line_net),
            ]
        )

    items_table = Table(
        rows,
        colWidths=[7 * mm, 48 * mm, 20 * mm, 18 * mm, 15 * mm, 15 * mm, 17 * mm, 14 * mm, 13 * mm, 18 * mm],
        repeatRows=1,
    )
    items_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                ("ALIGN", (4, 1), (-1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    elements.append(items_table)
    elements.append(Spacer(1, 8))

    totals = [
        ["Subtotal", _money(purchase.subtotal)],
        ["Discount", f"−{_money(purchase.discount_total)}"],
        ["Freight", f"+{_money(purchase.freight_total)}"],
        ["VAT", _money(purchase.vat_total)],
    ]
    if purchase.round_off:
        totals.append(["Round off", _money(purchase.round_off)])
    totals.extend(
        [
            ["Grand total", _money(purchase.grand_total)],
            ["Paid", _money(purchase.paid_total)],
            ["Outstanding", _money(purchase.outstanding)],
        ]
    )
    totals_table = Table(
        [[Paragraph(f"<b>{label}</b>", small), Paragraph(value, small)] for label, value in totals],
        colWidths=[30 * mm, 30 * mm],
        hAlign="RIGHT",
    )
    totals_table.setStyle(
        TableStyle([("ALIGN", (1, 0), (1, -1), "RIGHT"), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)])
    )
    elements.append(totals_table)

    if purchase.notes:
        elements.append(Spacer(1, 8))
        elements.append(Paragraph(f"Notes: {purchase.notes}", small))
    if purchase.cancel_reason:
        elements.append(Spacer(1, 4))
        elements.append(
            Paragraph(f"<b>Cancelled:</b> {purchase.cancel_reason}", small)
        )

    elements.append(Spacer(1, 18))
    elements.append(Paragraph("Received by ______________________", small))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Generated by Medicine Dealer ERP", small))

    document.build(elements)
    return buffer.getvalue()
