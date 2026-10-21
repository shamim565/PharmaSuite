"""Seed a deterministic demo dataset for local development and screenshots.

The command is idempotent: master data is matched by code/name, and every
business document carries a ``demo:`` idempotency key so re-running it will not
duplicate invoices, purchases, payments, returns, or expenses.

It is intended for a fresh development database. To start over, drop and
recreate the database (``docker compose -f infra/docker-compose.yml down -v``)
rather than trying to delete posted ledger entries.
"""

from __future__ import annotations

import os
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounting.models import AccountType, ExpenseCategory, FinancialAccount
from apps.accounting.services import post_account_transaction
from apps.accounts.models import Role, User, UserBranch, UserRole, UserStatus
from apps.branches.models import Branch, BranchType
from apps.catalog.models import (
    Generic,
    Manufacturer,
    Medicine,
    MedicineCategory,
    Unit,
    UnitType,
)
from apps.inventory.models import (
    AdjustmentReason,
    AdjustmentType,
    StockAdjustment,
    StockBalance,
)
from apps.inventory.services import create_stock_adjustment
from apps.payments.models import Cheque, Payment
from apps.payments.services import (
    clear_cheque,
    create_cheque,
    deposit_cheque,
    record_customer_payment,
)
from apps.purchases.models import Purchase, PurchaseItem
from apps.purchases.services import compute_line_totals, compute_purchase_totals, confirm_purchase
from apps.sales.models import (
    Customer,
    CustomerType,
    PriceTier,
    RefundMethod,
    ReturnCondition,
    SalesInvoice,
    SalesInvoiceItem,
    SalesReturnReason,
)
from apps.sales.services import (
    confirm_sale,
    confirm_sales_return,
    create_sales_return,
    resolve_unit_price,
)
from apps.suppliers.models import Supplier, SupplierType

DEMO_PREFIX = "demo:"
DEMO_PASSWORD = "Demo@1234"

# (name, strength, dosage form, generic, manufacturer, purchase price, pack size, category)
MEDICINES: list[tuple[str, str, str, str, str, str, str, str]] = [
    ("Paracetamol", "500 mg", "Tablet", "Paracetamol", "Square Pharmaceuticals", "2.10", "10", "Analgesics"),
    ("Paracetamol", "120 mg/5 ml", "Syrup", "Paracetamol", "Square Pharmaceuticals", "48.00", "1", "Analgesics"),
    ("Amoxicillin", "500 mg", "Capsule", "Amoxicillin", "Beximco Pharmaceuticals", "7.40", "10", "Antibiotics"),
    ("Azithromycin", "500 mg", "Tablet", "Azithromycin", "Incepta Pharmaceuticals", "28.00", "6", "Antibiotics"),
    ("Ciprofloxacin", "500 mg", "Tablet", "Ciprofloxacin", "Renata Limited", "9.50", "10", "Antibiotics"),
    ("Omeprazole", "20 mg", "Capsule", "Omeprazole", "Eskayef Pharmaceuticals", "5.60", "10", "Gastro"),
    ("Esomeprazole", "40 mg", "Tablet", "Esomeprazole", "Incepta Pharmaceuticals", "16.00", "10", "Gastro"),
    ("Metformin", "500 mg", "Tablet", "Metformin", "Square Pharmaceuticals", "3.20", "10", "Diabetes"),
    ("Glimepiride", "2 mg", "Tablet", "Glimepiride", "Beximco Pharmaceuticals", "8.90", "10", "Diabetes"),
    ("Amlodipine", "5 mg", "Tablet", "Amlodipine", "Renata Limited", "3.80", "10", "Cardiovascular"),
    ("Losartan", "50 mg", "Tablet", "Losartan", "Eskayef Pharmaceuticals", "6.20", "10", "Cardiovascular"),
    ("Atorvastatin", "20 mg", "Tablet", "Atorvastatin", "Incepta Pharmaceuticals", "12.50", "10", "Cardiovascular"),
    ("Cetirizine", "10 mg", "Tablet", "Cetirizine", "Square Pharmaceuticals", "2.40", "10", "Antihistamines"),
    ("Montelukast", "10 mg", "Tablet", "Montelukast", "Beximco Pharmaceuticals", "18.00", "10", "Respiratory"),
    ("Salbutamol", "100 mcg", "Inhaler", "Salbutamol", "Renata Limited", "285.00", "1", "Respiratory"),
    ("Diclofenac", "50 mg", "Tablet", "Diclofenac", "Eskayef Pharmaceuticals", "3.10", "10", "Analgesics"),
    ("Vitamin D3", "20000 IU", "Capsule", "Cholecalciferol", "Incepta Pharmaceuticals", "9.80", "4", "Vitamins"),
    ("Oral Rehydration Salt", "20.5 g", "Powder", "ORS", "Square Pharmaceuticals", "6.00", "1", "Rehydration"),
    ("Iron + Folic Acid", "200 mg", "Tablet", "Ferrous Fumarate", "Beximco Pharmaceuticals", "4.20", "10", "Vitamins"),
    ("Ceftriaxone", "1 g", "Injection", "Ceftriaxone", "Incepta Pharmaceuticals", "148.00", "1", "Antibiotics"),
]


class Command(BaseCommand):
    help = "Seed a demo branch network, catalog, stock, sales, payments and reports data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--owner-mobile",
            default=os.environ.get("OWNER_MOBILE", "01700000000"),
            help="Mobile number of the owner created by seed_rbac.",
        )
        parser.add_argument(
            "--skip-rbac",
            action="store_true",
            help="Skip the seed_rbac call (roles/permissions must already exist).",
        )
        parser.add_argument(
            "--keep-owner-password",
            action="store_true",
            help="Do not reset the owner password to the demo password.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        today = timezone.localdate()

        if not options["skip_rbac"]:
            call_command("seed_rbac")

        owner = User.objects.filter(mobile=options["owner_mobile"]).first()
        if owner is None:
            self.stderr.write(
                self.style.ERROR(
                    f"Owner {options['owner_mobile']} not found. Run `manage.py seed_rbac` first."
                )
            )
            return

        self.stdout.write("Seeding demo data…")

        if not options["keep_owner_password"]:
            owner.set_password(DEMO_PASSWORD)
            owner.must_change_password = False
            owner.save(update_fields=["password", "must_change_password", "updated_at"])

        branches = self._branches(owner)
        self._users(branches)
        self._accounts(branches)
        self._fund_accounts(branches, owner, today)
        medicines = self._catalog()
        suppliers = self._suppliers()
        customers = self._customers()
        purchases = self._purchases(branches, suppliers, medicines, owner, today)
        invoices = self._sales(branches, customers, medicines, owner, today)
        payments = self._payments(branches, customers, invoices, owner, today)
        cheques = self._cheques(branches, customers, invoices, owner, today)
        returns = self._returns(invoices, owner, today)
        adjustments = self._adjustments(branches, owner, today)
        expenses = self._expenses(branches, owner, today)

        self._summary(
            branches=branches,
            medicines=medicines,
            purchases=purchases,
            invoices=invoices,
            payments=payments,
            cheques=cheques,
            returns=returns,
            adjustments=adjustments,
            expenses=expenses,
            owner_mobile=options["owner_mobile"],
            keep_owner_password=options["keep_owner_password"],
        )

    # ------------------------------------------------------------------ setup

    def _branches(self, owner) -> dict[str, Branch]:
        main, _ = Branch.objects.get_or_create(
            code="MAIN",
            defaults={
                "name": "Head Office — Dhaka",
                "type": BranchType.HEAD_OFFICE,
                "invoice_prefix": "MAIN",
                "address": "Tejgaon Industrial Area, Dhaka",
                "phone": "+880 2 9000001",
                "manager": owner,
            },
        )
        dhk, _ = Branch.objects.get_or_create(
            code="DHK",
            defaults={
                "name": "Dhaka Depot",
                "type": BranchType.BRANCH,
                "invoice_prefix": "DHK",
                "address": "Mirpur, Dhaka",
                "phone": "+880 2 9000002",
            },
        )
        ctg, _ = Branch.objects.get_or_create(
            code="CTG",
            defaults={
                "name": "Chattogram Depot",
                "type": BranchType.BRANCH,
                "invoice_prefix": "CTG",
                "address": "Agrabad, Chattogram",
                "phone": "+880 31 700003",
            },
        )
        for branch in (main, dhk, ctg):
            if branch.manager_id is None:
                branch.manager = owner
                branch.save(update_fields=["manager", "updated_at"])
        return {"MAIN": main, "DHK": dhk, "CTG": ctg}

    def _users(self, branches: dict[str, Branch]) -> None:
        people = [
            ("01700000011", "Nusrat Jahan", "BRANCH_MANAGER", "DHK"),
            ("01700000012", "Rafiq Hasan", "ACCOUNTANT", "MAIN"),
            ("01700000013", "Sadia Islam", "SALES_OPERATOR", "DHK"),
            ("01700000014", "Jahid Hossain", "WAREHOUSE_MANAGER", "CTG"),
            ("01700000015", "Tanvir Ahmed", "SALES_REP", "DHK"),
            ("01700000016", "Farhana Akter", "MEDICAL_REP", "DHK"),
        ]
        for mobile, full_name, role_code, branch_code in people:
            user, created = User.objects.get_or_create(
                mobile=mobile,
                defaults={
                    "full_name": full_name,
                    "status": UserStatus.ACTIVE,
                    "default_branch": branches[branch_code],
                },
            )
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save(update_fields=["password"])
            role = Role.objects.filter(code=role_code).first()
            if role is not None:
                UserRole.objects.get_or_create(user=user, role=role)
            for code, branch in branches.items():
                UserBranch.objects.get_or_create(
                    user=user,
                    branch=branch,
                    defaults={"is_default": code == branch_code},
                )

    def _accounts(self, branches: dict[str, Branch]) -> None:
        for branch in branches.values():
            for suffix, name, account_type in (
                ("CASH", "Cash Counter", AccountType.CASH),
                ("BANK", "Bank Account", AccountType.BANK),
            ):
                FinancialAccount.objects.get_or_create(
                    code=f"{branch.code}-{suffix}",
                    defaults={
                        "name": f"{branch.name} — {name}",
                        "account_type": account_type,
                        "branch": branch,
                        "allow_negative": False,
                    },
                )

    def _fund_accounts(self, branches: dict[str, Branch], owner, today) -> None:
        """Give each account an opening balance so expenses can be posted."""
        for branch in branches.values():
            for suffix, amount in (("CASH", "250000.00"), ("BANK", "1500000.00")):
                account = FinancialAccount.objects.get(code=f"{branch.code}-{suffix}")
                key = f"demo:opening:{account.code}"
                if account.transactions.filter(idempotency_key=key).exists():
                    continue
                post_account_transaction(
                    account=account,
                    entry_type="OPENING",
                    amount_delta=Decimal(amount),
                    source_type="DEMO_OPENING",
                    reference="Demo opening balance",
                    business_date=today - timedelta(days=60),
                    actor=owner,
                    idempotency_key=key,
                )

    def _catalog(self) -> list[Medicine]:
        units = {
            "pc": Unit.objects.get_or_create(
                name="Piece", defaults={"symbol": "pc", "unit_type": UnitType.COUNT}
            )[0],
            "box": Unit.objects.get_or_create(
                name="Box", defaults={"symbol": "box", "unit_type": UnitType.COUNT}
            )[0],
            "bottle": Unit.objects.get_or_create(
                name="Bottle", defaults={"symbol": "btl", "unit_type": UnitType.VOLUME}
            )[0],
            "vial": Unit.objects.get_or_create(
                name="Vial", defaults={"symbol": "vial", "unit_type": UnitType.COUNT}
            )[0],
        }
        categories = {}
        for name in sorted({row[7] for row in MEDICINES}):
            categories[name] = MedicineCategory.objects.get_or_create(name=name)[0]

        medicines: list[Medicine] = []
        for index, (name, strength, form, generic_name, manufacturer_name, cost, pack, category) in enumerate(
            MEDICINES, start=1
        ):
            generic = Generic.objects.get_or_create(name=generic_name)[0]
            manufacturer = Manufacturer.objects.get_or_create(
                name=manufacturer_name, defaults={"country": "Bangladesh"}
            )[0]
            purchase_price = Decimal(cost)
            selling_price = (purchase_price * Decimal("1.18")).quantize(Decimal("0.01"))
            wholesale = (purchase_price * Decimal("1.12")).quantize(Decimal("0.01"))
            retail = (purchase_price * Decimal("1.25")).quantize(Decimal("0.01"))
            unit = units["vial"] if form == "Injection" else units["bottle"] if form in ("Syrup", "Inhaler") else units["pc"]
            medicine, _ = Medicine.objects.get_or_create(
                code=f"DEMO-{index:03d}",
                defaults={
                    "name": name,
                    "strength": strength,
                    "dosage_form": form,
                    "generic": generic,
                    "manufacturer": manufacturer,
                    "category": categories[category],
                    "base_unit": unit,
                    "pack_size": Decimal(pack),
                    "purchase_price": purchase_price,
                    "selling_price": selling_price,
                    "retail_price": retail,
                    "wholesale_price": wholesale,
                    "mrp": retail,
                    "vat_rate": Decimal("0"),
                    "reorder_level": Decimal("2000") if index == 1 else Decimal("50"),
                    "shelf_life_months": 24,
                    "near_expiry_days": 90,
                },
            )
            medicines.append(medicine)
        return medicines

    def _suppliers(self) -> list[Supplier]:
        rows = [
            ("DEMO-SUP-01", "Square Pharmaceuticals Ltd.", SupplierType.MANUFACTURER, 15),
            ("DEMO-SUP-02", "Beximco Pharmaceuticals Ltd.", SupplierType.MANUFACTURER, 30),
            ("DEMO-SUP-03", "Incepta Pharmaceuticals Ltd.", SupplierType.MANUFACTURER, 21),
        ]
        suppliers = []
        for code, name, supplier_type, credit_days in rows:
            supplier, _ = Supplier.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "supplier_type": supplier_type,
                    "credit_days": credit_days,
                    "phone": "+880 2 9880000",
                    "email": f"{code.lower()}@example.com",
                    "address": "Dhaka, Bangladesh",
                },
            )
            suppliers.append(supplier)
        return suppliers

    def _customers(self) -> list[Customer]:
        rows = [
            ("DEMO-CUS-01", "Green Cross Pharmacy", CustomerType.PHARMACY, PriceTier.RETAIL, 60, 15),
            ("DEMO-CUS-02", "Lazz Pharma — Mirpur", CustomerType.PHARMACY, PriceTier.WHOLESALE, 250, 30),
            ("DEMO-CUS-03", "Popular Diagnostic Centre", CustomerType.HOSPITAL, PriceTier.WHOLESALE, 400, 30),
            ("DEMO-CUS-04", "United Hospital Pharmacy", CustomerType.HOSPITAL, PriceTier.WHOLESALE, 350, 45),
            ("DEMO-CUS-05", "Al-Madina Pharmacy", CustomerType.PHARMACY, PriceTier.RETAIL, 40, 15),
            ("DEMO-CUS-06", "HealthPlus Retail", CustomerType.RETAIL, PriceTier.RETAIL, 20, 7),
            ("DEMO-CUS-07", "Chattogram Medical Store", CustomerType.PHARMACY, PriceTier.WHOLESALE, 120, 30),
            ("DEMO-CUS-08", "Care Zone Clinic", CustomerType.CLINIC, PriceTier.RETAIL, 30, 15),
        ]
        customers = []
        for code, name, customer_type, tier, limit, days in rows:
            customer, _ = Customer.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "customer_type": customer_type,
                    "price_tier": tier,
                    "credit_limit": Decimal(limit) * Decimal("1000"),
                    "credit_days": days,
                    "phone": "+880 17 0000 0000",
                    "email": f"{code.lower()}@example.com",
                    "area": "Dhaka" if "Chattogram" not in name else "Chattogram",
                },
            )
            customers.append(customer)
        return customers

    # ------------------------------------------------------------- documents

    def _purchases(self, branches, suppliers, medicines, owner, today) -> list[Purchase]:
        plan = [
            ("demo:purchase-1", "DHK", 0, 40, [0, 1, 2, 3, 4], "DEMO-PINV-1001"),
            ("demo:purchase-2", "DHK", 1, 18, [5, 6, 7, 8, 9], "DEMO-PINV-1002"),
            ("demo:purchase-3", "CTG", 2, 7, [10, 11, 12, 13, 19], "DEMO-PINV-1003"),
        ]
        created: list[Purchase] = []
        for key, branch_code, supplier_index, days_ago, medicine_indexes, invoice_no in plan:
            existing = Purchase.objects.filter(idempotency_key=key).first()
            if existing is not None:
                created.append(existing)
                continue
            branch = branches[branch_code]
            supplier = suppliers[supplier_index]
            business_date = today - timedelta(days=days_ago)
            purchase = Purchase.objects.create(
                branch=branch,
                supplier=supplier,
                supplier_invoice_number=invoice_no,
                supplier_invoice_date=business_date,
                business_date=business_date,
                notes="Demo seed purchase",
            )
            line_results = []
            for line_no, medicine_index in enumerate(medicine_indexes, start=1):
                medicine = medicines[medicine_index]
                qty = Decimal((line_no + 1) * 600)
                unit_cost = medicine.purchase_price
                # One batch per purchase is deliberately near expiry so the
                # dashboard and expiry report have something to show.
                expiry_days = 45 if (days_ago == 7 and line_no == 1) else 365 + line_no * 30
                calc = compute_line_totals(
                    {
                        "qty_entered": qty,
                        "bonus_qty_entered": Decimal("0"),
                        "conversion_factor": Decimal("1"),
                        "unit_cost": unit_cost,
                        "line_discount": Decimal("0"),
                        "vat_rate": Decimal("0"),
                    }
                )
                PurchaseItem.objects.create(
                    purchase=purchase,
                    line_no=line_no,
                    medicine=medicine,
                    batch_number=f"B{business_date:%y%m}{line_no:02d}",
                    manufacturing_date=business_date - timedelta(days=180),
                    expiry_date=today + timedelta(days=expiry_days),
                    qty_entered=qty,
                    qty_base=calc["qty_base"],
                    bonus_qty_entered=Decimal("0"),
                    bonus_qty_base=calc["bonus_qty_base"],
                    unit_cost=unit_cost,
                    vat_rate=Decimal("0"),
                    vat_amount=Decimal("0"),
                    line_net=calc["line_net"],
                    base_unit_cost=calc["base_unit_cost"],
                    effective_unit_cost=calc["effective_unit_cost"],
                )
                line_results.append(
                    {
                        "gross": (qty * unit_cost).quantize(Decimal("0.01")),
                        "line_discount": Decimal("0"),
                        "vat_amount": Decimal("0"),
                    }
                )
            totals = compute_purchase_totals(line_results, Decimal("0"))
            for field, value in totals.items():
                setattr(purchase, field, value)
            purchase.save()
            confirm_purchase(purchase=purchase, actor=owner, idempotency_key=key)
            created.append(purchase)
        return created

    def _sales(self, branches, customers, medicines, owner, today) -> list[SalesInvoice]:
        plan = [
            ("demo:sale-1", "DHK", 0, 14, [(0, 6), (5, 3)]),
            ("demo:sale-2", "DHK", 1, 11, [(2, 4), (7, 2), (9, 1)]),
            ("demo:sale-3", "CTG", 2, 8, [(10, 5), (11, 3)]),
            ("demo:sale-4", "DHK", 3, 5, [(8, 6), (4, 2)]),
            ("demo:sale-5", "DHK", 4, 2, [(0, 3), (6, 1)]),
            ("demo:sale-6", "CTG", 6, 0, [(12, 4), (13, 2)]),
        ]
        invoices: list[SalesInvoice] = []
        for key, branch_code, customer_index, days_ago, rows in plan:
            existing = SalesInvoice.objects.filter(idempotency_key=key).first()
            if existing is not None:
                invoices.append(existing)
                continue
            branch = branches[branch_code]
            customer = customers[customer_index]
            business_date = today - timedelta(days=days_ago)
            invoice = SalesInvoice.objects.create(
                branch=branch,
                customer=customer,
                business_date=business_date,
                notes="Demo seed invoice",
            )
            subtotal = Decimal("0")
            for line_no, (medicine_index, qty_raw) in enumerate(rows, start=1):
                medicine = medicines[medicine_index]
                qty = Decimal(qty_raw) * Decimal("100")
                unit_price = resolve_unit_price(medicine, customer)
                line_net = (unit_price * qty).quantize(Decimal("0.01"))
                SalesInvoiceItem.objects.create(
                    invoice=invoice,
                    line_no=line_no,
                    medicine=medicine,
                    batch_number="",
                    qty=qty,
                    unit_price=unit_price,
                    line_discount=Decimal("0"),
                    vat_rate=Decimal("0"),
                    vat_amount=Decimal("0"),
                    line_net=line_net,
                )
                subtotal += unit_price * qty
            grand_total = subtotal.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            invoice.subtotal = subtotal.quantize(Decimal("0.01"))
            invoice.discount_total = Decimal("0")
            invoice.vat_total = Decimal("0")
            invoice.round_off = (grand_total - subtotal).quantize(Decimal("0.01"))
            invoice.grand_total = grand_total
            invoice.due_date = business_date + timedelta(days=customer.credit_days)
            invoice.idempotency_key = key
            invoice.save()
            confirm_sale(invoice=invoice, actor=owner, idempotency_key=key)
            invoice.refresh_from_db()
            invoices.append(invoice)

        # One draft invoice so the UI shows the create/confirm workflow.
        draft_key = "demo:sale-draft"
        if not SalesInvoice.objects.filter(idempotency_key=draft_key).exists():
            branch = branches["DHK"]
            customer = customers[5]
            invoice = SalesInvoice.objects.create(
                branch=branch,
                customer=customer,
                business_date=today,
                notes="Demo draft — confirm this in the UI",
                idempotency_key=draft_key,
            )
            medicine = medicines[7]
            qty = Decimal("200")
            unit_price = resolve_unit_price(medicine, customer)
            SalesInvoiceItem.objects.create(
                invoice=invoice,
                line_no=1,
                medicine=medicine,
                batch_number="",
                qty=qty,
                unit_price=unit_price,
                line_discount=Decimal("0"),
                vat_rate=Decimal("0"),
                vat_amount=Decimal("0"),
                line_net=(unit_price * qty).quantize(Decimal("0.01")),
            )
            invoice.subtotal = (unit_price * qty).quantize(Decimal("0.01"))
            invoice.grand_total = (unit_price * qty).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            invoice.due_date = today + timedelta(days=customer.credit_days)
            invoice.save()
            invoices.append(invoice)

        return invoices

    def _payments(self, branches, customers, invoices, owner, today) -> list[Payment]:
        confirmed = [inv for inv in invoices if inv.lifecycle == "CONFIRMED" and inv.outstanding > 0]
        if not confirmed:
            return []
        plan = [
            ("demo:payment-1", 0, 0.60, "CASH", 6),
            ("demo:payment-2", 1, 0.40, "BANK", 4),
            ("demo:payment-3", 3, 0.30, "MFS", 0),
        ]
        payments: list[Payment] = []
        for key, invoice_index, share, method, days_ago in plan:
            if Payment.objects.filter(idempotency_key=key).exists():
                payments.append(Payment.objects.get(idempotency_key=key))
                continue
            invoice = confirmed[min(invoice_index, len(confirmed) - 1)]
            amount = (invoice.outstanding * Decimal(str(share))).quantize(Decimal("0.01"))
            if amount <= 0:
                continue
            payment = record_customer_payment(
                customer=invoice.customer,
                branch=invoice.branch,
                amount=amount,
                method=method,
                account=FinancialAccount.objects.get(code=f"{invoice.branch.code}-CASH" if method != "BANK" else f"{invoice.branch.code}-BANK"),
                business_date=today - timedelta(days=days_ago),
                reference=f"DEMO-RCPT-{len(payments) + 1:03d}",
                allocations=[{"invoice": invoice, "amount": amount}],
                actor=owner,
                idempotency_key=key,
            )
            payments.append(payment)
        return payments

    def _cheques(self, branches, customers, invoices, owner, today) -> list[Cheque]:
        confirmed = [inv for inv in invoices if inv.lifecycle == "CONFIRMED"]
        if not confirmed:
            return []
        invoice = confirmed[0]
        key = "demo:cheque-1"
        cheque = Cheque.objects.filter(idempotency_key=key).first()
        if cheque is None:
            cheque = create_cheque(
                validated={
                    "direction": "RECEIVED",
                    "number": "DEMO-CHQ-0001",
                    "bank_name": "City Bank",
                    "bank_branch": "Gulshan",
                    "amount": Decimal("15000.00"),
                    "date_issued": today - timedelta(days=3),
                    "customer": invoice.customer,
                    "invoice": invoice,
                    "idempotency_key": key,
                    "notes": "Demo post-dated cheque",
                },
                actor=owner,
            )
            deposit_cheque(cheque, owner, notes="Deposited by demo seed")
            clear_cheque(cheque, owner, notes="Cleared by demo seed")
        return [cheque]

    def _returns(self, invoices, owner, today) -> list:
        confirmed = [inv for inv in invoices if inv.lifecycle == "CONFIRMED"]
        if not confirmed:
            return []
        key = "demo:return-1"
        from apps.sales.models import SalesReturn

        existing = SalesReturn.objects.filter(
            idempotency_key__in=[key, f"{key}:confirm"]
        ).first()
        if existing is not None:
            if existing.status == "DRAFT":
                confirm_sales_return(sales_return=existing, actor=owner)
            return [existing]
        invoice = confirmed[0]
        item = invoice.items.first()
        if item is None:
            return []
        sales_return = create_sales_return(
            invoice=invoice,
            reason_code=SalesReturnReason.CUSTOMER_RETURN,
            refund_method=RefundMethod.ADJUST_DUES,
            business_date=today - timedelta(days=1),
            notes="Demo customer return",
            items_data=[
                {
                    "invoice_item": item.id,
                    "qty": Decimal("1"),
                    "condition": ReturnCondition.RESELLABLE,
                }
            ],
            actor=owner,
            idempotency_key=key,
        )
        confirm_sales_return(sales_return=sales_return, actor=owner)
        return [sales_return]

    def _adjustments(self, branches, owner, today) -> list:
        key = "demo:adjustment-1"
        from apps.inventory.models import StockAdjustment

        existing = StockAdjustment.objects.filter(idempotency_key=key).first()
        if existing is not None:
            return [existing]
        balance = (
            StockBalance.objects.filter(branch=branches["CTG"], qty_on_hand__gte=40)
            .select_related("medicine", "batch")
            .order_by("-batch__unit_cost")
            .first()
        )
        if balance is None:
            return []
        return [
            create_stock_adjustment(
                branch=branches["CTG"],
                adjustment_type=AdjustmentType.DECREASE,
                reason_code=AdjustmentReason.DAMAGE,
                business_date=today,
                notes="Demo damaged stock — awaiting approval",
                items_data=[
                    {
                        "medicine": balance.medicine,
                        "batch": balance.batch,
                        "qty": Decimal("40"),
                    }
                ],
                actor=owner,
                idempotency_key=key,
            )
        ]

    def _expenses(self, branches, owner, today) -> list:
        from apps.accounting.models import Expense
        from apps.accounting.services import create_expense

        created = []
        plan = [
            ("demo:expense-1", "Rent", "12000.00", "Monthly depot rent", today - timedelta(days=2)),
            ("demo:expense-2", "Transport", "1200.00", "Delivery fuel", today - timedelta(days=1)),
        ]
        for key, category_name, amount, note, business_date in plan:
            existing = Expense.objects.filter(idempotency_key=key).first()
            if existing is not None:
                created.append(existing)
                continue
            category = ExpenseCategory.objects.get(name=category_name)
            account = FinancialAccount.objects.get(code="MAIN-CASH")
            created.append(
                create_expense(
                    branch=branches["MAIN"],
                    category=category,
                    amount=Decimal(amount),
                    account=account,
                    business_date=business_date,
                    payee="Demo vendor",
                    reference=f"DEMO-EXP-{len(created) + 1:03d}",
                    note=note,
                    actor=owner,
                    idempotency_key=key,
                )
            )
        return created

    # ---------------------------------------------------------------- output

    def _summary(self, **kwargs) -> None:
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Demo seed complete"))
        self.stdout.write(f"  branches:   {Branch.objects.count()} ({', '.join(kwargs['branches'])})")
        self.stdout.write(f"  medicines:  {Medicine.objects.count()}")
        self.stdout.write(f"  purchases:  {Purchase.objects.count()}")
        self.stdout.write(f"  invoices:   {SalesInvoice.objects.count()}")
        self.stdout.write(f"  payments:   {Payment.objects.count()}")
        self.stdout.write(f"  cheques:    {Cheque.objects.count()}")
        self.stdout.write(f"  adjustments:{StockAdjustment.objects.count()}")
        self.stdout.write("")
        self.stdout.write("Login with any of these (all use the same demo password):")
        if kwargs["keep_owner_password"]:
            self.stdout.write(f"  owner        {kwargs['owner_mobile']}  / (unchanged)")
        else:
            self.stdout.write(f"  owner        {kwargs['owner_mobile']}  / {DEMO_PASSWORD}")
        self.stdout.write(f"  branch mgr   01700000011  / {DEMO_PASSWORD}")
        self.stdout.write(f"  accountant   01700000012  / {DEMO_PASSWORD}")
        self.stdout.write(f"  sales        01700000013  / {DEMO_PASSWORD}")
        self.stdout.write(f"  warehouse    01700000014  / {DEMO_PASSWORD}")
        self.stdout.write("")
        self.stdout.write("Next: `make up`, open http://localhost:3000 and log in.")
