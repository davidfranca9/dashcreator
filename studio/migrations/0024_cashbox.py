from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("studio", "0023_fixed_cost_due_month"),
    ]

    operations = [
        migrations.CreateModel(
            name="CashBox",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=120)),
                ("allocation_percentage", models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ("description", models.CharField(blank=True, default="", max_length=220)),
                ("icon", models.CharField(blank=True, default="ti-pig-money", max_length=60)),
                ("workspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="studio.workspace")),
            ],
            options={
                "ordering": ["name"],
                "unique_together": {("workspace", "name")},
            },
        ),
    ]
