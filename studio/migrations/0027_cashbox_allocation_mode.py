from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('studio', '0026_prospect_archive'),
    ]

    operations = [
        migrations.AddField(
            model_name='cashbox',
            name='allocation_mode',
            field=models.CharField(
                choices=[('percentage', '% do fluxo livre'), ('fixed', 'Valor fixo (R$)')],
                default='percentage',
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name='cashbox',
            name='allocation_amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
    ]
