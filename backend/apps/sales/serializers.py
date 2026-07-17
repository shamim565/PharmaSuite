from decimal import ROUND_HALF_UP, Decimal

from rest_framework import serializers

from apps.catalog.models import Medicine
from apps.sales.models import (
    Customer,
    CustomerLedgerEntry,
    SalesInvoice,
    SalesInvoiceItem,
    SalesInvoiceStatus,
)
from apps.sales.services import money, resolve_unit_price

TWO = Decimal("0.01")


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = [
            "id",
            "code",
            "name",
            "customer_type",
            "contact_person",
            "phone",
            "email",
            "address",
            "area",
            "price_tier",
            "default_discount_pct",
            "credit_limit",
            "credit_days",
            "credit_hold",
            "credit_hold_reason",
            "balance_cache",
            "is_active",
            "notes",
            "created_at",
        ]
        read_only_fields = ["id", "balance_cache", "created_at"]

    def validate_code(self, value: str) -> str:
        value = value.strip().upper()
        qs = Customer.objects.filter(code__iexact=value)
        if self.instance:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise serializers.ValidationError("A customer with this code already exists.")
        return value


class CustomerLedgerEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerLedgerEntry
        fields = [
            "id",
            "customer",
            "branch",
            "entry_type",
            "amount_delta",
            "due_date",
            "source_type",
            "source_number",
            "business_date",
            "created_at",
        ]


class SalesInvoiceItemReadSerializer(serializers.ModelSerializer):
    medicine_name = serializers.CharField(source="medicine.name", read_only=True)
    medicine_code = serializers.CharField(source="medicine.code", read_only=True)
    line_total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = SalesInvoiceItem
        fields = [
            "id",
            "line_no",
            "medicine",
            "medicine_name",
            "medicine_code",
            "batch",
            "batch_number",
            "qty",
            "unit_price",
            "line_discount",
            "vat_rate",
            "vat_amount",
            "line_net",
            "line_total",
            "unit_cost",
            "is_free_goods",
        ]


class SalesInvoiceReadSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    customer_code = serializers.CharField(source="customer.code", read_only=True)
    customer_phone = serializers.CharField(source="customer.phone", read_only=True)
    customer_address = serializers.CharField(source="customer.address", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    branch_address = serializers.CharField(source="branch.address", read_only=True)
    branch_phone = serializers.CharField(source="branch.phone", read_only=True)
    items = SalesInvoiceItemReadSerializer(many=True, read_only=True)
    outstanding = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = SalesInvoice
        fields = [
            "id",
            "number",
            "branch",
            "branch_name",
            "branch_address",
            "branch_phone",
            "customer",
            "customer_name",
            "customer_code",
            "customer_phone",
            "customer_address",
            "business_date",
            "lifecycle",
            "payment_status",
            "return_status",
            "fulfillment_status",
            "subtotal",
            "discount_total",
            "vat_total",
            "round_off",
            "grand_total",
            "paid_total",
            "outstanding",
            "due_date",
            "notes",
            "confirmed_at",
            "cancel_reason",
            "credit_override",
            "credit_override_reason",
            "created_at",
            "items",
        ]


class SalesInvoiceItemInputSerializer(serializers.Serializer):
    medicine = serializers.PrimaryKeyRelatedField(queryset=Medicine.objects.all())
    qty = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal("0.001"))
    unit_price = serializers.DecimalField(
        max_digits=14, decimal_places=4, required=False, allow_null=True, min_value=Decimal("0")
    )
    line_discount = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, default=Decimal("0"), min_value=Decimal("0")
    )
    vat_rate = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, allow_null=True
    )
    is_free_goods = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        if attrs.get("vat_rate") is None:
            attrs["vat_rate"] = attrs["medicine"].vat_rate
        if attrs.get("is_free_goods"):
            attrs["unit_price"] = Decimal("0")
            attrs["line_discount"] = Decimal("0")
            attrs["vat_rate"] = Decimal("0")
        return attrs


class SalesInvoiceWriteSerializer(serializers.Serializer):
    customer = serializers.UUIDField()
    branch = serializers.UUIDField()
    business_date = serializers.DateField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    items = SalesInvoiceItemInputSerializer(many=True, allow_empty=False)

    def validate_customer(self, value):
        customer = Customer.objects.filter(id=value, is_active=True).first()
        if customer is None:
            raise serializers.ValidationError("Customer not found or inactive.")
        self._customer = customer
        return value

    def validate_branch(self, value):
        from apps.branches.models import Branch

        branch = Branch.objects.filter(id=value).first()
        if branch is None:
            raise serializers.ValidationError("Branch not found.")
        self._branch = branch
        return value

    def _build_rows(self, items_data):
        rows = []
        for item in items_data:
            unit_price = item.get("unit_price")
            if unit_price is None and not item.get("is_free_goods"):
                unit_price = resolve_unit_price(item["medicine"], self._customer)
            unit_price = Decimal(unit_price or 0)
            qty = Decimal(item["qty"])
            gross = money(qty * unit_price)
            discount = money(item.get("line_discount") or 0)
            taxable = money(gross - discount)
            vat_rate = Decimal(item.get("vat_rate") or 0)
            vat_amount = money(taxable * vat_rate / Decimal("100"))
            rows.append(
                {
                    "input": item,
                    "unit_price": unit_price,
                    "gross": gross,
                    "line_discount": discount,
                    "vat_rate": vat_rate,
                    "vat_amount": vat_amount,
                    "line_net": taxable,
                }
            )
        return rows

    def _totals(self, rows):
        subtotal = sum((row["gross"] for row in rows), Decimal("0"))
        discount_total = sum((row["line_discount"] for row in rows), Decimal("0"))
        vat_total = sum((row["vat_amount"] for row in rows), Decimal("0"))
        net_total = money(subtotal - discount_total + vat_total)
        grand_total = net_total.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return {
            "subtotal": money(subtotal),
            "discount_total": money(discount_total),
            "vat_total": money(vat_total),
            "round_off": money(grand_total - net_total),
            "grand_total": money(grand_total),
        }

    def _persist_items(self, invoice: SalesInvoice, rows) -> None:
        for line_no, row in enumerate(rows, start=1):
            item = row["input"]
            SalesInvoiceItem.objects.create(
                invoice=invoice,
                line_no=line_no,
                medicine=item["medicine"],
                batch=None,
                batch_number="",
                qty=item["qty"],
                unit_price=row["unit_price"],
                line_discount=row["line_discount"],
                vat_rate=row["vat_rate"],
                vat_amount=row["vat_amount"],
                line_net=row["line_net"],
                is_free_goods=item.get("is_free_goods", False),
            )

    def create(self, validated_data):
        from django.utils import timezone

        items_data = validated_data.pop("items")
        rows = self._build_rows(items_data)
        totals = self._totals(rows)
        invoice = SalesInvoice.objects.create(
            customer=self._customer,
            branch=self._branch,
            business_date=validated_data.get("business_date") or timezone.localdate(),
            notes=validated_data.get("notes", ""),
            **totals,
        )
        self._persist_items(invoice, rows)
        return invoice

    def update(self, instance: SalesInvoice, validated_data):
        if instance.lifecycle != SalesInvoiceStatus.DRAFT:
            raise serializers.ValidationError("Only draft invoices can be edited.")
        items_data = validated_data.pop("items")
        rows = self._build_rows(items_data)
        totals = self._totals(rows)

        instance.customer = getattr(self, "_customer", instance.customer)
        instance.branch = getattr(self, "_branch", instance.branch)
        if validated_data.get("business_date"):
            instance.business_date = validated_data["business_date"]
        if "notes" in validated_data:
            instance.notes = validated_data["notes"]
        for field, value in totals.items():
            setattr(instance, field, value)
        instance.save()

        instance.items.all().delete()
        self._persist_items(instance, rows)
        return instance
