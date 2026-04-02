from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("studio", "0012_alter_prospect_stage_financeentry"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="contract_status",
            field=models.CharField(
                choices=[
                    ("pending", "Pendente"),
                    ("generated", "Contrato gerado"),
                    ("dismissed", "Dispensado"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
    ]
