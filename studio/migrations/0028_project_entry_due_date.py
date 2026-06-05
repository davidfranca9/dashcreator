from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('studio', '0027_cashbox_allocation_mode'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='entry_due_date',
            field=models.DateField(blank=True, null=True),
        ),
    ]
