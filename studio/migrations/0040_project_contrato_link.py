from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("studio", "0039_seed_default_funnels"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="contrato_link",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
    ]
