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

from apps.accounting.models import (
    AccountType,
    ExpenseCategory,
    FinancialAccount,
    Income,
    IncomeCategory,
)
from apps.accounting.services import create_income, post_account_transaction
from apps.accounts.models import Role, User, UserBranch, UserRole, UserStatus
from apps.branches.models import Branch, BranchType
from apps.catalog.models import (
    Generic,
    Manufacturer,
    Medicine,
    MedicineBatch,
    MedicineCategory,
    Unit,
    UnitType,
)
from apps.doctors.models import (
    Doctor,
    DoctorCategory,
    DoctorChamber,
    DoctorMedicine,
    DoctorType,
    DoctorVisit,
    VisitOutcome,
    VisitStatus,
)
from apps.doctors.services import complete_visit, mark_visit_missed
from apps.inventory.models import (
    AdjustmentReason,
    AdjustmentStatus,
    AdjustmentType,
    EntryType,
    StockAdjustment,
    StockBalance,
    StockPool,
    StockTransfer,
    WarehouseLocation,
)
from apps.inventory.services import (
    MovementLine,
    approve_stock_adjustment,
    confirm_stock_transfer,
    create_stock_adjustment,
    create_stock_transfer,
    post_transactions,
)
from apps.payments.models import Cheque, Payment
from apps.payments.services import (
    clear_cheque,
    create_cheque,
    deposit_cheque,
    record_customer_payment,
)
from apps.purchases.credit_models import SupplierCreditNote, SupplierCreditNoteReason
from apps.purchases.credit_services import (
    create_supplier_credit_note,
    settle_supplier_credit_note,
)
from apps.purchases.models import Purchase, PurchaseItem
from apps.purchases.po_models import PurchaseOrder
from apps.purchases.po_services import (
    approve_purchase_order,
    convert_po_to_purchase,
    create_purchase_order,
    submit_purchase_order,
)
from apps.purchases.services import compute_line_totals, compute_purchase_totals, confirm_purchase
from apps.representatives.models import (
    AssignmentEntityType,
    Representative,
    RepresentativeAssignment,
    RepresentativeType,
    SalesTarget,
    Territory,
    TerritoryType,
)
from apps.representatives.services import assign
from apps.sales.delivery_models import DeliveryChallan
from apps.sales.delivery_services import (
    complete_delivery_challan,
    create_challan_from_invoice,
    dispatch_delivery_challan,
)
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
        reps = self._representatives(branches, customers, today)
        purchases = self._purchases(branches, suppliers, medicines, owner, today)
        locations = self._warehouse_locations(branches)
        purchase_orders = self._purchase_orders(branches, suppliers, medicines, owner, today)
        invoices = self._sales(branches, customers, medicines, owner, today, reps)
        payments = self._payments(branches, customers, invoices, owner, today)
        cheques = self._cheques(branches, customers, invoices, owner, today)
        returns = self._returns(invoices, owner, today)
        adjustments = self._adjustments(branches, owner, today)
        expiry_adjustment = self._expiry_adjustment(branches, owner, today)
        credit_notes = self._supplier_credit_notes(
            branches, suppliers, expiry_adjustment, owner, today
        )
        deliveries = self._deliveries(invoices, owner, today)
        targets = self._sales_targets(reps, branches, today)
        doctors = self._doctors_and_visits(reps, medicines, branches, owner, today)
        transfers = self._stock_transfers(branches, owner, today)
        expenses = self._expenses(branches, owner, today)
        incomes = self._income(branches, owner, today)

        self._summary(
            branches=branches,
            medicines=medicines,
            purchases=purchases,
            purchase_orders=purchase_orders,
            invoices=invoices,
            deliveries=deliveries,
            payments=payments,
            cheques=cheques,
            returns=returns,
            adjustments=adjustments,
            credit_notes=credit_notes,
            targets=targets,
            reps=reps,
            doctors=doctors,
            transfers=transfers,
            expenses=expenses,
            incomes=incomes,
            locations=locations,
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
                    # Azithromycin and Ceftriaxone are demo Rx-only medicines.
                    "rx_required": index in (4, 20),
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

    def _sales(self, branches, customers, medicines, owner, today, reps=None) -> list[SalesInvoice]:
        sales_reps = (reps or {}).get("sales") or []
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
                sales_rep=sales_reps[0] if branch_code == "DHK" and sales_reps else None,
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

        # An invoice confirmed with an explicit batch (FEFO override) so the
        # Exceptions report and audit trail have a real example.
        exception_key = "demo:sale-exception-1"
        if not SalesInvoice.objects.filter(idempotency_key=exception_key).exists():
            branch = branches["DHK"]
            customer = customers[1]
            balance = (
                StockBalance.objects.filter(branch=branch, qty_on_hand__gte=50)
                .select_related("medicine", "batch")
                .order_by("created_at")
                .first()
            )
            if balance is not None:
                qty = Decimal("20")
                unit_price = resolve_unit_price(balance.medicine, customer)
                invoice = SalesInvoice.objects.create(
                    branch=branch,
                    customer=customer,
                    business_date=today - timedelta(days=4),
                    notes="Demo: customer requested a later-expiry batch",
                    fefo_override=True,
                    fefo_override_reason="Customer requested a specific batch",
                    idempotency_key=exception_key,
                )
                SalesInvoiceItem.objects.create(
                    invoice=invoice,
                    line_no=1,
                    medicine=balance.medicine,
                    batch=balance.batch,
                    batch_number=balance.batch.batch_number,
                    qty=qty,
                    unit_price=unit_price,
                    line_discount=Decimal("0"),
                    vat_rate=Decimal("0"),
                    vat_amount=Decimal("0"),
                    line_net=(unit_price * qty).quantize(Decimal("0.01")),
                )
                invoice.subtotal = (unit_price * qty).quantize(Decimal("0.01"))
                invoice.grand_total = (unit_price * qty).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                invoice.due_date = invoice.business_date + timedelta(days=customer.credit_days)
                invoice.save()
                confirm_sale(invoice=invoice, actor=owner, idempotency_key=exception_key)
                invoice.refresh_from_db()
                invoices.append(invoice)

        # A draft containing an Rx-only medicine — confirm it in the UI to see
        # the prescription number / doctor requirement and the audited override.
        rx_key = "demo:sale-rx-draft"
        if not SalesInvoice.objects.filter(idempotency_key=rx_key).exists():
            branch = branches["DHK"]
            customer = customers[2]
            rx_medicine = medicines[3]  # Azithromycin (rx_required)
            balance = (
                StockBalance.objects.filter(
                    branch=branch, medicine=rx_medicine, qty_on_hand__gte=20
                )
                .select_related("batch")
                .first()
            )
            if balance is not None:
                invoice = SalesInvoice.objects.create(
                    branch=branch,
                    customer=customer,
                    business_date=today,
                    notes="Demo Rx draft — confirm with a prescription number",
                    idempotency_key=rx_key,
                )
                qty = Decimal("10")
                unit_price = resolve_unit_price(rx_medicine, customer)
                SalesInvoiceItem.objects.create(
                    invoice=invoice,
                    line_no=1,
                    medicine=rx_medicine,
                    batch_number="",
                    qty=qty,
                    unit_price=unit_price,
                    line_discount=Decimal("0"),
                    vat_rate=Decimal("0"),
                    vat_amount=Decimal("0"),
                    line_net=(unit_price * qty).quantize(Decimal("0.01")),
                )
                invoice.subtotal = (unit_price * qty).quantize(Decimal("0.01"))
                invoice.grand_total = (unit_price * qty).quantize(
                    Decimal("1"), rounding=ROUND_HALF_UP
                )
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

    # ------------------------------------------------------------ people / CRM

    def _representatives(self, branches, customers, today) -> dict:
        region = Territory.objects.get_or_create(
            name="Dhaka Region",
            parent=None,
            defaults={"territory_type": TerritoryType.REGION},
        )[0]
        area = Territory.objects.get_or_create(
            name="Dhaka Metro",
            parent=region,
            defaults={"territory_type": TerritoryType.AREA},
        )[0]
        dhk_territory = Territory.objects.get_or_create(
            name="Mirpur–Uttara",
            parent=area,
            defaults={"territory_type": TerritoryType.TERRITORY},
        )[0]
        ctg_region = Territory.objects.get_or_create(
            name="Chattogram Region",
            parent=None,
            defaults={"territory_type": TerritoryType.REGION},
        )[0]
        ctg_territory = Territory.objects.get_or_create(
            name="Agrabad–Pahartali",
            parent=ctg_region,
            defaults={"territory_type": TerritoryType.TERRITORY},
        )[0]

        sales_user = User.objects.filter(mobile="01700000015").first()
        medical_user = User.objects.filter(mobile="01700000016").first()

        def rep(code, name, rep_type, branch_code, territory, user=None, phone=""):
            representative, _ = Representative.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "rep_type": rep_type,
                    "branch": branches[branch_code],
                    "user": user,
                    "phone": phone,
                    "joined_at": today - timedelta(days=420),
                },
            )
            if representative.user_id is None and user is not None:
                representative.user = user
                representative.save(update_fields=["user", "updated_at"])
            if not RepresentativeAssignment.objects.filter(
                representative=representative,
                entity_type=AssignmentEntityType.TERRITORY,
                entity_id=territory.id,
                effective_to__isnull=True,
            ).exists():
                assign(
                    representative=representative,
                    entity_type=AssignmentEntityType.TERRITORY,
                    entity_id=territory.id,
                    effective_from=today - timedelta(days=400),
                )
            return representative

        sales_rep_dhk = rep(
            "REP-001", "Rakibul Hasan", RepresentativeType.SALES, "DHK",
            dhk_territory, sales_user, "+880 1711 100001",
        )
        sales_rep_ctg = rep(
            "REP-002", "Sumaiya Akter", RepresentativeType.SALES, "CTG",
            ctg_territory, None, "+880 1711 100002",
        )
        medical_rep = rep(
            "REP-003", "Dr. Imran Chowdhury", RepresentativeType.MEDICAL, "DHK",
            dhk_territory, medical_user, "+880 1711 100003",
        )

        # Customer coverage for the Dhaka rep (first three customers).
        for customer in customers[:3]:
            if not RepresentativeAssignment.objects.filter(
                representative=sales_rep_dhk,
                entity_type=AssignmentEntityType.CUSTOMER,
                entity_id=customer.id,
                effective_to__isnull=True,
            ).exists():
                assign(
                    representative=sales_rep_dhk,
                    entity_type=AssignmentEntityType.CUSTOMER,
                    entity_id=customer.id,
                    effective_from=today - timedelta(days=300),
                )

        return {
            "sales": [sales_rep_dhk, sales_rep_ctg],
            "medical": [medical_rep],
            "territories": {
                "dhk": dhk_territory,
                "ctg": ctg_territory,
            },
        }

    def _warehouse_locations(self, branches) -> list[WarehouseLocation]:
        locations: list[WarehouseLocation] = []
        layout = [("A", "R1", "B1"), ("A", "R1", "B2"), ("A", "R2", "B1"), ("B", "R1", "B1")]
        for branch in branches.values():
            for zone, rack, bin_code in layout:
                location, _ = WarehouseLocation.objects.get_or_create(
                    branch=branch,
                    zone=zone,
                    rack=rack,
                    bin=bin_code,
                )
                locations.append(location)

        # Assign a location label to seeded batches that do not have one.
        for branch in branches.values():
            labels = [loc.label for loc in locations if loc.branch_id == branch.id]
            batches = MedicineBatch.objects.filter(branch=branch, location="").order_by("created_at")
            for index, batch in enumerate(batches):
                batch.location = labels[index % len(labels)]
                batch.save(update_fields=["location", "updated_at"])
        return locations

    # ------------------------------------------------------- procurement / ops

    def _purchase_orders(self, branches, suppliers, medicines, owner, today) -> list[PurchaseOrder]:
        plan = [
            ("demo:po-1", "DHK", 0, [0, 1], "DRAFT"),
            ("demo:po-2", "DHK", 1, [2, 3], "SUBMITTED"),
            ("demo:po-3", "CTG", 2, [10, 11], "APPROVED"),
            ("demo:po-4", "DHK", 0, [6, 7], "FULLY_RECEIVED"),
        ]
        orders: list[PurchaseOrder] = []
        for key, branch_code, supplier_index, medicine_indexes, target_status in plan:
            existing = PurchaseOrder.objects.filter(idempotency_key=key).first()
            if existing is not None:
                orders.append(existing)
                continue

            po = create_purchase_order(
                branch=branches[branch_code],
                supplier=suppliers[supplier_index],
                business_date=today - timedelta(days=2),
                expected_delivery_date=today + timedelta(days=5),
                notes="Demo purchase order",
                items=[
                    {
                        "medicine": medicines[index],
                        "qty_ordered": Decimal("300"),
                        "unit_cost": medicines[index].purchase_price,
                        "line_discount": Decimal("0"),
                        "vat_rate": Decimal("0"),
                    }
                    for index in medicine_indexes
                ],
                actor=owner,
                idempotency_key=key,
            )
            if target_status in ("SUBMITTED", "APPROVED", "FULLY_RECEIVED"):
                po = submit_purchase_order(purchase_order=po, actor=owner)
            if target_status in ("APPROVED", "FULLY_RECEIVED"):
                po = approve_purchase_order(purchase_order=po, actor=owner)
            if target_status == "FULLY_RECEIVED":
                grn = convert_po_to_purchase(
                    purchase_order=po,
                    actor=owner,
                    supplier_invoice_number=f"DEMO-PO-GRN-{po.id.hex[:6].upper()}",
                    supplier_invoice_date=today - timedelta(days=1),
                    idempotency_key="demo:po-4:convert",
                )
                if grn.lifecycle == "DRAFT":
                    confirm_purchase(
                        purchase=grn,
                        actor=owner,
                        idempotency_key="demo:po-4:convert:confirm",
                    )
                orders.append(po)
                continue
            orders.append(po)
        return orders

    def _expiry_adjustment(self, branches, owner, today) -> StockAdjustment | None:
        key = "demo:expiry-adjustment-1"
        existing = StockAdjustment.objects.filter(idempotency_key=key).first()
        if existing is not None:
            return existing

        balance = (
            StockBalance.objects.filter(branch=branches["DHK"], qty_on_hand__gte=60)
            .select_related("medicine", "batch")
            .order_by("-batch__expiry_date")
            .first()
        )
        if balance is None:
            return None
        adjustment = create_stock_adjustment(
            branch=branches["DHK"],
            adjustment_type=AdjustmentType.DECREASE,
            reason_code=AdjustmentReason.EXPIRY_WRITE_OFF,
            business_date=today - timedelta(days=1),
            notes="Demo expired stock write-off (approved, returnable to supplier)",
            items_data=[
                {
                    "medicine": balance.medicine,
                    "batch": balance.batch,
                    "qty": Decimal("20"),
                }
            ],
            actor=owner,
            idempotency_key=key,
        )
        approver = User.objects.filter(mobile="01700000011").first()
        if (
            adjustment.status == AdjustmentStatus.PENDING_APPROVAL
            and approver is not None
        ):
            approve_stock_adjustment(adjustment=adjustment, actor=approver)
            adjustment.refresh_from_db()
        return adjustment

    def _supplier_credit_notes(self, branches, suppliers, expiry_adjustment, owner, today) -> list:
        notes = []
        open_key = "demo:credit-note-1"
        existing = SupplierCreditNote.objects.filter(idempotency_key=open_key).first()
        if existing is None:
            existing = create_supplier_credit_note(
                branch=branches["DHK"],
                supplier=suppliers[0],
                business_date=today - timedelta(days=1),
                amount=(expiry_adjustment.total_value if expiry_adjustment else Decimal("850.00")),
                reason_code=SupplierCreditNoteReason.EXPIRY_RETURN,
                reference="SUP-CN-EXP-001",
                notes="Credit for expired stock returned to manufacturer",
                adjustment=expiry_adjustment,
                actor=owner,
                idempotency_key=open_key,
            )
        notes.append(existing)

        settled_key = "demo:credit-note-2"
        existing_settled = SupplierCreditNote.objects.filter(
            idempotency_key=settled_key
        ).first()
        if existing_settled is None:
            existing_settled = create_supplier_credit_note(
                branch=branches["DHK"],
                supplier=suppliers[1],
                business_date=today - timedelta(days=10),
                amount=Decimal("1200.00"),
                reason_code=SupplierCreditNoteReason.DAMAGED_RETURN,
                reference="SUP-CN-DMG-002",
                notes="Credit received for damaged cartons",
                actor=owner,
                idempotency_key=settled_key,
            )
            settle_supplier_credit_note(credit_note=existing_settled, actor=owner)
            existing_settled.refresh_from_db()
        notes.append(existing_settled)
        return notes

    def _deliveries(self, invoices, owner, today) -> list[DeliveryChallan]:
        confirmed = [invoice for invoice in invoices if invoice.lifecycle == "CONFIRMED"]
        challans: list[DeliveryChallan] = []
        plan = [
            ("demo:challan-1", 0, "PREPARED", "Karim Mia", "DHK-T-11"),
            ("demo:challan-2", 1, "DISPATCHED", "Shafiq Ahmed", "DHK-T-12"),
            ("demo:challan-3", 2, "DELIVERED", "Rafiqul Islam", "DHK-T-13"),
        ]
        for key, invoice_index, target_status, driver, vehicle in plan:
            existing = DeliveryChallan.objects.filter(idempotency_key=key).first()
            if existing is not None:
                challans.append(existing)
                continue
            if invoice_index >= len(confirmed):
                continue
            challan = create_challan_from_invoice(
                invoice=confirmed[invoice_index],
                delivery_person=driver,
                delivery_phone="+880 1811 20000" + str(invoice_index),
                vehicle_no=vehicle,
                notes="Demo delivery run",
                actor=owner,
                idempotency_key=key,
            )
            if target_status in ("DISPATCHED", "DELIVERED"):
                challan = dispatch_delivery_challan(challan=challan, actor=owner)
            if target_status == "DELIVERED":
                challan = complete_delivery_challan(
                    challan=challan,
                    actor=owner,
                    recipient_name="Demo Recipient",
                    recipient_phone="+880 1811 29999",
                )
            challans.append(challan)
        return challans

    def _sales_targets(self, reps, branches, today) -> list[SalesTarget]:
        targets = []
        plan = [
            (reps["sales"][0], branches["DHK"], "25000.00", "20000.00", 80),
            (reps["sales"][1], branches["CTG"], "30000.00", "24000.00", 60),
            (reps["medical"][0], branches["DHK"], "0.00", "0.00", 40),
        ]
        for representative, branch, amount, collection, visits in plan:
            target, _ = SalesTarget.objects.get_or_create(
                representative=representative,
                fiscal_year=today.year,
                period_month=today.month,
                defaults={
                    "branch": branch,
                    "target_amount": Decimal(amount),
                    "target_collection": Decimal(collection),
                    "target_visits": visits,
                    "notes": "Demo monthly target",
                },
            )
            targets.append(target)
        return targets

    def _doctors_and_visits(self, reps, medicines, branches, owner, today) -> dict:
        medical_rep = reps["medical"][0]
        dhk = branches["DHK"]
        territory = reps["territories"]["dhk"]

        doctors = []
        for code, name, specialty, category in (
            ("DOC-001", "Dr. Ayesha Rahman", "Cardiology", DoctorCategory.A),
            ("DOC-002", "Dr. Mahmudul Karim", "Medicine", DoctorCategory.B),
        ):
            doctor, _ = Doctor.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "specialty": specialty,
                    "degrees": "MBBS, FCPS",
                    "doctor_type": DoctorType.CONSULTANT,
                    "category": category,
                    "potential_rating": "High" if category == DoctorCategory.A else "Medium",
                    "territory": territory,
                    "visit_frequency_target": 4 if category == DoctorCategory.A else 2,
                    "phones": ["+880 1911 300001"],
                },
            )
            DoctorChamber.objects.get_or_create(
                doctor=doctor,
                name=f"{name} Chamber",
                defaults={
                    "address": "Dhanmondi, Dhaka",
                    "visiting_hours": "6:00 PM – 9:00 PM",
                },
            )
            for medicine_index in (0, 5, 9):
                DoctorMedicine.objects.get_or_create(
                    doctor=doctor,
                    medicine=medicines[medicine_index],
                    effective_from=today - timedelta(days=90),
                    defaults={"priority": "First line", "strength_note": "As prescribed"},
                )
            if not RepresentativeAssignment.objects.filter(
                representative=medical_rep,
                entity_type=AssignmentEntityType.DOCTOR,
                entity_id=doctor.id,
                effective_to__isnull=True,
            ).exists():
                assign(
                    representative=medical_rep,
                    entity_type=AssignmentEntityType.DOCTOR,
                    entity_id=doctor.id,
                    effective_from=today - timedelta(days=120),
                )
            doctors.append(doctor)

        # Promo stock for sample dispensing (doctor visits issue from PROMO).
        sample_balance = (
            StockBalance.objects.filter(branch=dhk, qty_on_hand__gte=50)
            .select_related("medicine", "batch")
            .order_by("created_at")
            .first()
        )
        if sample_balance is not None:
            post_transactions(
                branch=dhk,
                lines=[
                    MovementLine(
                        medicine=sample_balance.medicine,
                        batch=sample_balance.batch,
                        qty_delta=Decimal("100"),
                        unit_cost=sample_balance.batch.unit_cost,
                        pool=StockPool.PROMO,
                    )
                ],
                entry_type=EntryType.BONUS,
                source_type="DEMO_PROMO_STOCK",
                source_number="DEMO-PROMO-1",
                business_date=today - timedelta(days=20),
                actor=owner,
                idempotency_key="demo:promo-stock-1",
            )

        visits = []
        completed_plan = (
            doctors[0], today - timedelta(days=3), VisitOutcome.PRESCRIBING,
            "Detail: antihypertensives",
        )
        existing_completed = DoctorVisit.objects.filter(
            doctor=completed_plan[0],
            representative=medical_rep,
            planned_date=completed_plan[1],
        ).first()
        if existing_completed is None:
            visit = DoctorVisit.objects.create(
                doctor=completed_plan[0],
                representative=medical_rep,
                branch=dhk,
                planned_date=completed_plan[1],
                purpose="Demo visit",
                created_by=owner,
            )
            samples = []
            if sample_balance is not None:
                samples = [
                    {
                        "medicine": sample_balance.medicine,
                        "batch": sample_balance.batch,
                        "qty": Decimal("5"),
                    }
                ]
            visit = complete_visit(
                visit=visit,
                actor=owner,
                visited_at=timezone.now() - timedelta(days=3),
                purpose=completed_plan[3],
                products_discussed=[medicines[0].name, medicines[9].name],
                outcome=completed_plan[2],
                next_visit_date=today + timedelta(days=14),
                notes="Demo completed visit",
                samples=samples,
            )
            visits.append(visit)
        else:
            visits.append(existing_completed)

        missed_date = today - timedelta(days=1)
        existing_missed = DoctorVisit.objects.filter(
            doctor=doctors[1], representative=medical_rep, planned_date=missed_date
        ).first()
        if existing_missed is None:
            missed = DoctorVisit.objects.create(
                doctor=doctors[1],
                representative=medical_rep,
                branch=dhk,
                planned_date=missed_date,
                purpose="Demo planned visit",
                created_by=owner,
            )
            missed = mark_visit_missed(
                visit=missed, reason="Doctor unavailable — emergency surgery", actor=owner
            )
            visits.append(missed)
        else:
            visits.append(existing_missed)

        planned_date = today + timedelta(days=2)
        existing_planned = DoctorVisit.objects.filter(
            doctor=doctors[0], representative=medical_rep, planned_date=planned_date
        ).first()
        if existing_planned is None:
            planned = DoctorVisit.objects.create(
                doctor=doctors[0],
                representative=medical_rep,
                branch=dhk,
                planned_date=planned_date,
                purpose="Follow-up on new prescriptions",
                created_by=owner,
            )
            visits.append(planned)
        else:
            visits.append(existing_planned)

        return {"doctors": doctors, "visits": visits}

    def _stock_transfers(self, branches, owner, today) -> list[StockTransfer]:
        key = "demo:transfer-1"
        existing = StockTransfer.objects.filter(idempotency_key=key).first()
        if existing is not None:
            return [existing]
        balance = (
            StockBalance.objects.filter(branch=branches["DHK"], qty_on_hand__gte=100)
            .select_related("medicine", "batch")
            .order_by("created_at")
            .first()
        )
        if balance is None:
            return []
        transfer = create_stock_transfer(
            from_branch=branches["DHK"],
            to_branch=branches["CTG"],
            business_date=today - timedelta(days=1),
            notes="Demo inter-branch replenishment",
            items_data=[
                {
                    "medicine": balance.medicine,
                    "batch": balance.batch,
                    "qty": Decimal("50"),
                }
            ],
            actor=owner,
            idempotency_key=key,
        )
        transfer = confirm_stock_transfer(transfer=transfer, actor=owner)
        return [transfer]

    def _income(self, branches, owner, today) -> list:
        created = []
        plan = [
            ("demo:income-1", "Interest income", "2500.00", "MAIN-BANK", "Bank interest", 5),
            ("demo:income-2", "Scrap sales", "800.00", "MAIN-CASH", "Empty carton sale", 1),
        ]
        for key, category_name, amount, account_code, source, days_ago in plan:
            existing = Income.objects.filter(idempotency_key=key).first()
            if existing is not None:
                created.append(existing)
                continue
            category, _ = IncomeCategory.objects.get_or_create(name=category_name)
            account = FinancialAccount.objects.get(code=account_code)
            created.append(
                create_income(
                    branch=branches["MAIN"],
                    category=category,
                    amount=Decimal(amount),
                    account=account,
                    business_date=today - timedelta(days=days_ago),
                    source=source,
                    reference=f"DEMO-INC-{len(created) + 1:03d}",
                    note="Demo income",
                    actor=owner,
                    idempotency_key=key,
                )
            )
        return created

    # ---------------------------------------------------------------- output

    def _summary(self, **kwargs) -> None:
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Demo seed complete"))
        self.stdout.write(f"  branches:        {Branch.objects.count()} ({', '.join(kwargs['branches'])})")
        self.stdout.write(f"  medicines:       {Medicine.objects.count()}")
        self.stdout.write(f"  representatives: {Representative.objects.count()}")
        self.stdout.write(f"  doctors:         {Doctor.objects.count()}")
        self.stdout.write(f"  purchases:       {Purchase.objects.count()}")
        self.stdout.write(f"  purchase orders: {PurchaseOrder.objects.count()}")
        self.stdout.write(f"  invoices:        {SalesInvoice.objects.count()}")
        self.stdout.write(f"  deliveries:      {DeliveryChallan.objects.count()}")
        self.stdout.write(f"  payments:        {Payment.objects.count()}")
        self.stdout.write(f"  cheques:         {Cheque.objects.count()}")
        self.stdout.write(f"  returns:         {len(kwargs.get('returns') or [])}")
        self.stdout.write(f"  adjustments:     {StockAdjustment.objects.count()}")
        self.stdout.write(f"  credit notes:    {SupplierCreditNote.objects.count()}")
        self.stdout.write(f"  targets:         {SalesTarget.objects.count()}")
        self.stdout.write(f"  visits:          {DoctorVisit.objects.count()}")
        self.stdout.write(f"  transfers:       {StockTransfer.objects.count()}")
        self.stdout.write(f"  locations:       {WarehouseLocation.objects.count()}")
        self.stdout.write(f"  income:          {Income.objects.count()}")
        self.stdout.write(f"  expenses:        {kwargs['expenses'] and len(kwargs['expenses'])}")
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
        self.stdout.write(f"  sales rep    01700000015  / {DEMO_PASSWORD}")
        self.stdout.write(f"  medical rep  01700000016  / {DEMO_PASSWORD}")
        self.stdout.write("")
        self.stdout.write("Next: `make up`, open http://localhost:3000 and log in.")
