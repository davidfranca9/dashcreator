from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("studio", "0035_pageevent"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="image_rights_dismissed",
            field=models.BooleanField(default=False),
        ),
    ]
