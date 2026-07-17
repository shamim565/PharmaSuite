from decimal import Decimal

from django.db import models

from apps.common.models import BaseModel


class UnitType(models.TextChoices):
    COUNT = "COUNT", "Count"
    WEIGHT = "WEIGHT", "Weight"
    VOLUME = "VOLUME", "Volume"


class BatchStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    DEPLETED = "DEPLETED", "Depleted"
    EXPIRED = "EXPIRED", "Expired"
    QUARANTINE = "QUARANTINE", "Quarantine"
    DAMAGED = "DAMAGED", "Damaged"
    RECALLED = "RECALLED", "Recalled"


class BarcodeType(models.TextChoices):
    PRIMARY = "PRIMARY", "Primary"
    ALT = "ALT", "Alternate"


class Generic(BaseModel):
    name = models.CharField(max_length=200, unique=True)
    therapeutic_class = models.CharField(max_length=150, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "generics"

    def __str__(self) -> str:
        return self.name


class Manufacturer(BaseModel):
    name = models.CharField(max_length=200, unique=True)
    country = models.CharField(max_length=100, blank=True)
    license_no = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class MedicineCategory(BaseModel):
    name = models.CharField(max_length=150)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="children"
    )
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "medicine categories"
        constraints = [
            models.UniqueConstraint(fields=["parent", "name"], name="uq_category_parent_name")
        ]

    def __str__(self) -> str:
        return self.name


class Unit(BaseModel):
    name = models.CharField(max_length=50, unique=True)
    symbol = models.CharField(max_length=20, blank=True)
    unit_type = models.CharField(max_length=10, choices=UnitType.choices, default=UnitType.COUNT)
    allows_fraction = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.symbol or self.name


class Medicine(BaseModel):
    """Catalog item with normalized master references."""

    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=200, db_index=True)
    strength = models.CharField(max_length=100, blank=True)
    dosage_form = models.CharField(max_length=50, blank=True)

    generic = models.ForeignKey(
        Generic, null=True, blank=True, on_delete=models.PROTECT, related_name="medicines"
    )
    manufacturer = models.ForeignKey(
        Manufacturer, null=True, blank=True, on_delete=models.PROTECT, related_name="medicines"
    )
    category = models.ForeignKey(
        MedicineCategory, null=True, blank=True, on_delete=models.PROTECT, related_name="medicines"
    )
    base_unit = models.ForeignKey(
        Unit, null=True, blank=True, on_delete=models.PROTECT, related_name="medicines"
    )

    pack_size = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal("1"))
    purchase_price = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    selling_price = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    retail_price = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    wholesale_price = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    custom_price = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    mrp = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("15"))
    reorder_level = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal("0"))
    shelf_life_months = models.PositiveIntegerField(null=True, blank=True)
    near_expiry_days = models.PositiveIntegerField(null=True, blank=True)
    no_batch = models.BooleanField(default=False)
    rx_required = models.BooleanField(default=False)
    cold_chain = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["is_active"])]
        constraints = [
            models.CheckConstraint(condition=models.Q(purchase_price__gte=0), name="ck_medicine_purchase_nonneg"),
            models.CheckConstraint(condition=models.Q(selling_price__gte=0), name="ck_medicine_selling_nonneg"),
            models.CheckConstraint(condition=models.Q(mrp__gte=0), name="ck_medicine_mrp_nonneg"),
            models.CheckConstraint(condition=models.Q(reorder_level__gte=0), name="ck_medicine_reorder_nonneg"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class MedicineUnitConversion(BaseModel):
    medicine = models.ForeignKey(
        Medicine, on_delete=models.CASCADE, related_name="conversions"
    )
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name="conversions")
    factor_to_base = models.DecimalField(max_digits=18, decimal_places=6)
    is_purchase_default = models.BooleanField(default=False)
    is_sale_default = models.BooleanField(default=False)

    class Meta:
        ordering = ["medicine", "unit"]
        constraints = [
            models.UniqueConstraint(fields=["medicine", "unit"], name="uq_medicine_unit_conversion"),
            models.CheckConstraint(
                condition=models.Q(factor_to_base__gt=0), name="ck_conversion_factor_positive"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.medicine.code}: 1 {self.unit} = {self.factor_to_base} base"


class MedicineBarcode(BaseModel):
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE, related_name="barcodes")
    barcode = models.CharField(max_length=64, unique=True)
    barcode_type = models.CharField(
        max_length=10, choices=BarcodeType.choices, default=BarcodeType.PRIMARY
    )

    class Meta:
        ordering = ["medicine", "barcode"]

    def __str__(self) -> str:
        return self.barcode


class MedicineBatch(BaseModel):
    branch = models.ForeignKey(
        "branches.Branch", on_delete=models.PROTECT, related_name="medicine_batches"
    )
    medicine = models.ForeignKey(Medicine, on_delete=models.PROTECT, related_name="batches")
    batch_number = models.CharField(max_length=60, default="DEFAULT")
    manufacturing_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    qty_received_total = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal("0"))
    qty_on_hand = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal("0"))
    unit_cost = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("0"))
    status = models.CharField(max_length=15, choices=BatchStatus.choices, default=BatchStatus.ACTIVE)
    notes = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["medicine", "expiry_date"]
        verbose_name_plural = "medicine batches"
        constraints = [
            models.UniqueConstraint(
                fields=["branch", "medicine", "batch_number", "expiry_date"],
                name="uq_batch_identity",
            ),
            models.CheckConstraint(
                condition=models.Q(qty_on_hand__gte=0), name="ck_batch_qty_on_hand_nonneg"
            ),
            models.CheckConstraint(
                condition=models.Q(qty_received_total__gte=0),
                name="ck_batch_qty_received_nonneg",
            ),
        ]
        indexes = [
            models.Index(fields=["branch", "medicine", "expiry_date", "status"]),
            models.Index(fields=["expiry_date"]),
        ]

    def __str__(self) -> str:
        return f"{self.medicine.code} / {self.batch_number} / {self.expiry_date or 'no expiry'}"
