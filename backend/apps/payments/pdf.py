"""Customer payment (money receipt) PDF rendering (reportlab)."""

from decimal import Decimal
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.common.settings_service import get_setting_value
from apps.payments.models import PaymentMethod

METHOD_LABEL = dict(PaymentMethod.choices)


def _money(value) -> str:
    return f"{Decimal(value or 0):,.2f}"


def _date(value) -> str:
    return value.strftime("%d %b %Y") if value else "—"


def _company_line() -> str:
    parts = [
        get_setting_value("COMPANY_ADDRESS", default="") or "",
        get_setting_value("COMPANY_PHONE", default="") or "",
        f"BIN: {get_setting_value('COMPANY_BIN', default='')}" if get_setting_value("COMPANY_BIN") else "",
    ]
    return " · ".join(part for part in parts if part)


def build_receipt_pdf(payment) -> bytes:
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Receipt {payment.number or payment.id}",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReceiptTitle", parent=styles["Title"], fontSize=16, spaceAfter=2
    )
    small = ParagraphStyle("Small", parent=styles["BodyText"], fontSize=8, textColor=colors.grey)
    body = styles["BodyText"]
    amount_style = ParagraphStyle(
        "Amount", parent=styles["Title"], fontSize=18, alignment=1, spaceBefore=4, spaceAfter=4
    )

    company_name = get_setting_value("COMPANY_NAME", default="") or "PharmaSuite"
    elements = [
        Paragraph(company_name, title_style),
        Paragraph(_company_line(), small),
        Spacer(1, 6),
        Paragraph("<b>MONEY RECEIPT</b>", body),
        Spacer(1, 4),
    ]

    meta_rows = [
        ["Receipt", payment.number or "—"],
        ["Date", _date(payment.business_date)],
        ["Status", "REVERSED" if payment.status == "REVERSED" else "ACTIVE"],
        ["Branch", f"{payment.branch.name} {payment.branch.phone or ''}".strip()],
    ]
    party_rows = [
        ["Received from", f"{payment.customer.name} ({payment.customer.code})"],
        ["Phone", payment.customer.phone or "—"],
        ["Method", METHOD_LABEL.get(payment.method, payment.method)],
        ["Account", payment.account.name],
    ]
    if payment.reference:
        party_rows.append(["Reference", payment.reference])
    if payment.collector_id:
        party_rows.append(["Collected by", payment.collector.full_name if payment.collector else "—"])

    meta_table = Table(
        [[Paragraph(f"<b>{label}</b>", small), Paragraph(str(value), small)] for label, value in meta_rows],
        colWidths=[25 * mm, 62 * mm],
    )
    party_table = Table(
        [[Paragraph(f"<b>{label}</b>", small), Paragraph(str(value), small)] for label, value in party_rows],
        colWidths=[25 * mm, 62 * mm],
    )
    header_table = Table([[party_table, meta_table]], colWidths=[92 * mm, 88 * mm])
    header_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    elements.append(header_table)
    elements.append(Spacer(1, 12))

    amount_table = Table(
        [[Paragraph(f"<b>Amount received: BDT {_money(payment.amount)}</b>", amount_style)]],
        colWidths=[174 * mm],
    )
    amount_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    elements.append(amount_table)
    elements.append(Spacer(1, 12))

    allocations = list(payment.allocations.select_related("invoice").order_by("created_at"))
    if allocations:
        rows = [["Applied to invoice", "Amount"]]
        for allocation in allocations:
            rows.append(
                [
                    allocation.invoice.number or str(allocation.invoice_id),
                    _money(allocation.amount),
                ]
            )
        allocations_table = Table(rows, colWidths=[120 * mm, 54 * mm], hAlign="LEFT")
        allocations_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                ]
            )
        )
        elements.append(allocations_table)
    else:
        elements.append(
            Paragraph("Held as advance on account (not allocated to an invoice).", small)
        )

    if payment.status == "REVERSED":
        elements.append(Spacer(1, 8))
        elements.append(Paragraph("<b>This receipt was REVERSED.</b>", small))
        if payment.reversal_reason:
            elements.append(Paragraph(f"Reason: {payment.reversal_reason}", small))

    elements.append(Spacer(1, 24))
    signature_table = Table(
        [
            [
                Paragraph("Received by ______________________", small),
                Paragraph("Authorised signature ______________________", small),
            ]
        ],
        colWidths=[87 * mm, 87 * mm],
    )
    elements.append(signature_table)
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Generated by PharmaSuite", small))

    document.build(elements)
    return buffer.getvalue()
