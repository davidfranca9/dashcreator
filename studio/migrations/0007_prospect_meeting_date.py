from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("studio", "0006_project_closing_source_project_niche"),
    ]

    operations = [
        migrations.AddField(
            model_name="prospect",
            name="meeting_date",
            field=models.DateField(blank=True, null=True),
        ),
    ]
