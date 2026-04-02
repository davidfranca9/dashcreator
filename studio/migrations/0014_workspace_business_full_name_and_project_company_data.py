from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("studio", "0013_project_contract_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="workspace",
            name="business_full_name",
            field=models.CharField(blank=True, default="", max_length=160),
        ),
        migrations.AddField(
            model_name="project",
            name="company_address",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="project",
            name="company_cnpj",
            field=models.CharField(blank=True, default="", max_length=18),
        ),
        migrations.AddField(
            model_name="project",
            name="company_legal_name",
            field=models.CharField(blank=True, default="", max_length=180),
        ),
        migrations.AddField(
            model_name="project",
            name="company_phone",
            field=models.CharField(blank=True, default="", max_length=40),
        ),
    ]
