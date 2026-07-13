from decimal import Decimal

from django.db import models

from apps.common.models import BaseModel


class Medicine(BaseModel):
    """Catalog item. Full catalog normalization (generics, manufacturers, units)
    arrives in the catalog sprint; this model is the stable core."""

    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=200, db_index=True)
    generic_name = models.CharField(max_length=200, blank=True, db_index=True)
    manufacturer = models.CharField(max_length=200, blank=True)
    category = models.CharField(max_length=100, blank=True)
    strength = models.CharField(max_length=100, blank=True)
    dosage_form = models.CharField(max_length=50, blank=True)
    unit = models.CharField(max_length=20, default="pcs")
    pack_size = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal("1"))
    purchase_price = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    selling_price = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    mrp = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("15"))
    reorder_level = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal("0"))
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
