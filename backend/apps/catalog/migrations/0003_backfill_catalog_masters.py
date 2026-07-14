from django.db import migrations


def backfill_catalog_masters(apps, schema_editor):
    Medicine = apps.get_model("catalog", "Medicine")
    Generic = apps.get_model("catalog", "Generic")
    Manufacturer = apps.get_model("catalog", "Manufacturer")
    MedicineCategory = apps.get_model("catalog", "MedicineCategory")
    Unit = apps.get_model("catalog", "Unit")

    for medicine in Medicine.objects.all():
        updated_fields: list[str] = []

        if medicine.generic_name and not medicine.generic_id:
            generic, _ = Generic.objects.get_or_create(name=medicine.generic_name.strip())
            medicine.generic_id = generic.id
            updated_fields.append("generic")

        if medicine.manufacturer and not medicine.manufacturer_ref_id:
            manufacturer, _ = Manufacturer.objects.get_or_create(name=medicine.manufacturer.strip())
            medicine.manufacturer_ref_id = manufacturer.id
            updated_fields.append("manufacturer_ref")

        if medicine.category and not medicine.category_ref_id:
            category, _ = MedicineCategory.objects.get_or_create(
                name=medicine.category.strip(), parent=None
            )
            medicine.category_ref_id = category.id
            updated_fields.append("category_ref")

        if medicine.unit and not medicine.base_unit_id:
            unit, _ = Unit.objects.get_or_create(name=medicine.unit.strip())
            medicine.base_unit_id = unit.id
            updated_fields.append("base_unit")

        if updated_fields:
            medicine.save(update_fields=updated_fields)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0002_generic_manufacturer_unit_medicine_cold_chain_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_catalog_masters, noop),
    ]
