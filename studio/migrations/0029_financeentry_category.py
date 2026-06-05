from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('studio', '0028_project_entry_due_date'),
    ]

    operations = [
        migrations.AddField(
            model_name='financeentry',
            name='category',
            field=models.CharField(
                blank=True,
                choices=[
                    ('prolabore', 'Pró-labore'),
                    ('fixed_cost', 'Custo fixo'),
                    ('reserve', 'Reserva de emergência'),
                    ('investment', 'Investimento no negócio'),
                    ('free_flow', 'Fluxo livre'),
                    ('custom', 'Caixinha personalizada'),
                ],
                default='',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='financeentry',
            name='cash_box',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='finance_entries',
                to='studio.cashbox',
            ),
        ),
    ]
