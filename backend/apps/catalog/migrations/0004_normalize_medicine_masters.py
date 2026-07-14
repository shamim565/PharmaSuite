from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0003_backfill_catalog_masters"),
    ]

    operations = [
        migrations.RemoveField(model_name="medicine", name="generic_name"),
        migrations.RemoveField(model_name="medicine", name="manufacturer"),
        migrations.RemoveField(model_name="medicine", name="category"),
        migrations.RemoveField(model_name="medicine", name="unit"),
        migrations.RenameField(
            model_name="medicine", old_name="manufacturer_ref", new_name="manufacturer"
        ),
        migrations.RenameField(
            model_name="medicine", old_name="category_ref", new_name="category"
        ),
    ]
