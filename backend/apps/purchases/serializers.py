from decimal import Decimal

from rest_framework import serializers

from apps.catalog.models import Medicine
from apps.purchases.models import (
    Purchase,
    PurchaseItem,
    PurchaseReturn,
    PurchaseReturnItem,
    PurchaseStatus,
    SupplierPayment,
    SupplierPaymentAllocation,
)
from apps.purchases.services import compute_line_totals, compute_purchase_totals, money


class PurchaseItemReadSerializer(serializers.ModelSerializer):
    medicine_name = serializers.CharField(source="medicine.name", read_only=True)
    medicine_code = serializers.CharField(source="medicine.code", read_only=True)

    class Meta:
        model = PurchaseItem
        fields = [
            "id",
            "line_no",
            "medicine",
            "medicine_name",
            "medicine_code",
            "batch",
            "batch_number",
            "manufacturing_date",
            "expiry_date",
            "conversion_factor",
            "qty_entered",
            "qty_base",
            "bonus_qty_entered",
            "bonus_qty_base",
            "unit_cost",
            "line_discount",
            "vat_rate",
            "vat_amount",
            "line_net",
            "base_unit_cost",
            "effective_unit_cost",
            "returned_qty_base",
        ]


class PurchaseReadSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    confirmed_by_name = serializers.CharField(
        source="confirmed_by.full_name", read_only=True, default=""
    )
    items = PurchaseItemReadSerializer(many=True, read_only=True)
    outstanding = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = Purchase
        fields = [
            "id",
            "number",
            "branch",
            "branch_name",
            "supplier",
            "supplier_name",
            "supplier_invoice_number",
            "supplier_invoice_date",
            "business_date",
            "lifecycle",
            "payment_status",
            "return_status",
            "subtotal",
            "discount_total",
            "vat_total",
            "freight_total",
            "round_off",
            "grand_total",
            "paid_total",
            "returned_total",
            "outstanding",
            "notes",
            "confirmed_at",
            "confirmed_by_name",
            "cancel_reason",
            "created_at",
            "items",
        ]


class PurchaseItemInputSerializer(serializers.Serializer):
    medicine = serializers.PrimaryKeyRelatedField(queryset=Medicine.objects.all())
    batch_number = serializers.CharField(max_length=60)
    manufacturing_date = serializers.DateField(required=False, allow_null=True)
    expiry_date = serializers.DateField(required=False, allow_null=True)
    entry_unit = serializers.UUIDField(required=False, allow_null=True)
    conversion_factor = serializers.DecimalField(
        max_digits=18, decimal_places=6, required=False, default=Decimal("1")
    )
    qty_entered = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal("0.001"))
    bonus_qty_entered = serializers.DecimalField(
        max_digits=14, decimal_places=3, required=False, default=Decimal("0"), min_value=Decimal("0")
    )
    unit_cost = serializers.DecimalField(max_digits=14, decimal_places=4, min_value=Decimal("0"))
    line_discount = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, default=Decimal("0"), min_value=Decimal("0")
    )
    vat_rate = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, allow_null=True
    )

    def validate(self, attrs):
        medicine = attrs["medicine"]
        expiry = attrs.get("expiry_date")
        if not medicine.no_batch and not expiry:
            raise serializers.ValidationError(
                {"expiry_date": "Expiry date is required for this medicine."}
            )
        if expiry and attrs.get("manufacturing_date") and expiry < attrs["manufacturing_date"]:
            raise serializers.ValidationError(
                {"expiry_date": "Expiry date must be on or after the manufacturing date."}
            )
        if attrs.get("vat_rate") is None:
            attrs["vat_rate"] = medicine.vat_rate
        return attrs


class PurchaseWriteSerializer(serializers.Serializer):
    supplier = serializers.UUIDField()
    branch = serializers.UUIDField()
    supplier_invoice_number = serializers.CharField(max_length=60)
    supplier_invoice_date = serializers.DateField()
    business_date = serializers.DateField(required=False)
    freight_total = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, default=Decimal("0"), min_value=Decimal("0")
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    items = PurchaseItemInputSerializer(many=True, allow_empty=False)

    def validate_supplier(self, value):
        from apps.suppliers.models import Supplier

        supplier = Supplier.objects.filter(id=value, is_active=True).first()
        if supplier is None:
            raise serializers.ValidationError("Supplier not found or inactive.")
        self._supplier = supplier
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
            line = compute_line_totals(
                {
                    "qty_entered": item["qty_entered"],
                    "bonus_qty_entered": item.get("bonus_qty_entered") or 0,
                    "conversion_factor": item.get("conversion_factor") or 1,
                    "unit_cost": item["unit_cost"],
                    "line_discount": item.get("line_discount") or 0,
                    "vat_rate": item.get("vat_rate"),
                }
            )
            rows.append(
                {
                    "input": item,
                    "gross": money(Decimal(item["qty_entered"]) * Decimal(item["unit_cost"])),
                    "line_discount": money(item.get("line_discount") or 0),
                    **line,
                }
            )
        return rows

    def _persist_items(self, purchase: Purchase, rows) -> None:
        for line_no, row in enumerate(rows, start=1):
            item = row["input"]
            PurchaseItem.objects.create(
                purchase=purchase,
                line_no=line_no,
                medicine=item["medicine"],
                batch_number=item["batch_number"],
                manufacturing_date=item.get("manufacturing_date"),
                expiry_date=item.get("expiry_date"),
                entry_unit_id=item.get("entry_unit"),
                conversion_factor=item.get("conversion_factor") or Decimal("1"),
                qty_entered=item["qty_entered"],
                qty_base=row["qty_base"],
                bonus_qty_entered=item.get("bonus_qty_entered") or Decimal("0"),
                bonus_qty_base=row["bonus_qty_base"],
                unit_cost=item["unit_cost"],
                line_discount=row["line_discount"],
                vat_rate=row["vat_rate"],
                vat_amount=row["vat_amount"],
                line_net=row["line_net"],
                base_unit_cost=row["base_unit_cost"],
                effective_unit_cost=row["effective_unit_cost"],
            )

    def create(self, validated_data):
        from django.utils import timezone

        items_data = validated_data.pop("items")
        freight = validated_data.pop("freight_total") or Decimal("0")
        rows = self._build_rows(items_data)
        totals = compute_purchase_totals(rows, freight)

        purchase = Purchase.objects.create(
            supplier=self._supplier,
            branch=self._branch,
            supplier_invoice_number=validated_data["supplier_invoice_number"],
            supplier_invoice_date=validated_data["supplier_invoice_date"],
            business_date=validated_data.get("business_date") or timezone.localdate(),
            freight_total=totals["freight_total"],
            subtotal=totals["subtotal"],
            discount_total=totals["discount_total"],
            vat_total=totals["vat_total"],
            round_off=totals["round_off"],
            grand_total=totals["grand_total"],
            notes=validated_data.get("notes", ""),
        )
        self._persist_items(purchase, rows)
        return purchase

    def update(self, instance: Purchase, validated_data):
        if instance.lifecycle != PurchaseStatus.DRAFT:
            raise serializers.ValidationError("Only draft purchases can be edited.")

        items_data = validated_data.pop("items")
        freight = validated_data.pop("freight_total") or Decimal("0")
        rows = self._build_rows(items_data)
        totals = compute_purchase_totals(rows, freight)

        instance.supplier = getattr(self, "_supplier", instance.supplier)
        instance.branch = getattr(self, "_branch", instance.branch)
        for field in ("supplier_invoice_number", "supplier_invoice_date", "notes"):
            if field in validated_data:
                setattr(instance, field, validated_data[field])
        if validated_data.get("business_date"):
            instance.business_date = validated_data["business_date"]
        for field, value in totals.items():
            setattr(instance, field, value)
        instance.save()

        instance.items.all().delete()
        self._persist_items(instance, rows)
        return instance


class SupplierPaymentAllocationInputSerializer(serializers.Serializer):
    purchase = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))


class SupplierPaymentCreateSerializer(serializers.Serializer):
    supplier = serializers.UUIDField()
    branch = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    method = serializers.ChoiceField(choices=["CASH", "BANK", "MFS", "CHEQUE"])
    account = serializers.UUIDField()
    business_date = serializers.DateField(required=False)
    reference = serializers.CharField(required=False, allow_blank=True, default="")
    allocations = SupplierPaymentAllocationInputSerializer(many=True, required=False, allow_null=True)


class SupplierPaymentAllocationReadSerializer(serializers.ModelSerializer):
    purchase_number = serializers.CharField(source="purchase.number", read_only=True)

    class Meta:
        model = SupplierPaymentAllocation
        fields = ["id", "purchase", "purchase_number", "amount"]


class SupplierPaymentReadSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    account_name = serializers.CharField(source="account.name", read_only=True)
    allocations = SupplierPaymentAllocationReadSerializer(many=True, read_only=True)

    class Meta:
        model = SupplierPayment
        fields = [
            "id",
            "number",
            "branch",
            "branch_name",
            "supplier",
            "supplier_name",
            "business_date",
            "amount",
            "method",
            "account",
            "account_name",
            "reference",
            "status",
            "allocations",
            "created_at",
        ]


class PurchaseReturnItemInputSerializer(serializers.Serializer):
    purchase_item = serializers.UUIDField()
    qty = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal("0.001"))


class PurchaseReturnCreateSerializer(serializers.Serializer):
    purchase = serializers.UUIDField()
    reason_code = serializers.ChoiceField(
        choices=["DAMAGED", "EXPIRED", "NEAR_EXPIRY_AGREEMENT", "WRONG_ITEM", "OVER_SUPPLY"]
    )
    business_date = serializers.DateField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    items = PurchaseReturnItemInputSerializer(many=True, allow_empty=False)

    def validate(self, attrs):
        purchase = Purchase.objects.filter(id=attrs["purchase"]).first()
        if purchase is None:
            raise serializers.ValidationError({"purchase": "Purchase not found."})
        if purchase.lifecycle != PurchaseStatus.CONFIRMED:
            raise serializers.ValidationError({"purchase": "Only confirmed purchases can be returned."})
        self._purchase = purchase

        seen = set()
        for row in attrs["items"]:
            if str(row["purchase_item"]) in seen:
                raise serializers.ValidationError({"items": "Duplicate return lines are not allowed."})
            seen.add(str(row["purchase_item"]))
            item = PurchaseItem.objects.filter(id=row["purchase_item"], purchase=purchase).first()
            if item is None:
                raise serializers.ValidationError({"items": "Return line does not belong to the purchase."})
            if item.batch_id is None:
                raise serializers.ValidationError({"items": "Purchase line has no batch."})
            if row["qty"] > item.returnable_qty_base:
                raise serializers.ValidationError(
                    {"items": f"Line {item.line_no}: max returnable is {item.returnable_qty_base}."}
                )
            row["_item"] = item
        return attrs

    def create(self, validated_data):
        from django.utils import timezone

        purchase = self._purchase
        purchase_return = PurchaseReturn.objects.create(
            purchase=purchase,
            supplier=purchase.supplier,
            branch=purchase.branch,
            business_date=validated_data.get("business_date") or timezone.localdate(),
            reason_code=validated_data["reason_code"],
            notes=validated_data.get("notes", ""),
        )
        for row in validated_data["items"]:
            item = row["_item"]
            PurchaseReturnItem.objects.create(
                purchase_return=purchase_return,
                purchase_item=item,
                batch=item.batch,
                qty=row["qty"],
            )
        return purchase_return


class PurchaseReturnItemReadSerializer(serializers.ModelSerializer):
    medicine_name = serializers.CharField(source="purchase_item.medicine.name", read_only=True)
    medicine_code = serializers.CharField(source="purchase_item.medicine.code", read_only=True)
    line_no = serializers.IntegerField(source="purchase_item.line_no", read_only=True)

    class Meta:
        model = PurchaseReturnItem
        fields = [
            "id",
            "purchase_item",
            "line_no",
            "medicine_name",
            "medicine_code",
            "batch",
            "qty",
            "unit_cost",
            "vat_amount",
            "line_total",
        ]


class PurchaseReturnReadSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    purchase_number = serializers.CharField(source="purchase.number", read_only=True)
    items = PurchaseReturnItemReadSerializer(many=True, read_only=True)

    class Meta:
        model = PurchaseReturn
        fields = [
            "id",
            "number",
            "purchase",
            "purchase_number",
            "supplier",
            "supplier_name",
            "branch",
            "business_date",
            "reason_code",
            "status",
            "subtotal",
            "vat_total",
            "round_off",
            "grand_total",
            "notes",
            "confirmed_at",
            "created_at",
            "items",
        ]
