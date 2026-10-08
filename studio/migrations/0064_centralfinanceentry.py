from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("studio", "0063_lista_de_presenca")]

    operations = [
        migrations.CreateModel(
            name="CentralFinanceEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("kind", models.CharField(choices=[("income", "Entrada"), ("expense", "Saída"), ("fixed", "Custo fixo")], max_length=20)),
                ("product", models.CharField(max_length=120)),
                ("description", models.CharField(blank=True, default="", max_length=180)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("occurred_on", models.DateField()),
            ],
            options={"ordering": ["-occurred_on", "-pk"]},
        ),
    ]
