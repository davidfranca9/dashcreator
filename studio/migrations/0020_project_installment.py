# Cria o modelo ProjectInstallment (parcelas dinâmicas, brief Dash Creator
# seção 4.1) e converte cada projeto existente em até 2 parcelas: entrada
# (entry_value na close_date) + saldo (total - entry_value na payment_due_date
# ou close_date). Projetos sem total_value não geram parcelas.

import django.db.models.deletion
from django.db import migrations, models


def backfill_installments_from_project(apps, schema_editor):
    Project = apps.get_model("studio", "Project")
    Installment = apps.get_model("studio", "ProjectInstallment")
    received = (Installment.objects.first() is not None)
    if received:
        return  # já tem parcelas; não recria
    for project in Project.objects.iterator():
        total = project.total_value or 0
        entry = project.entry_value or 0
        if total <= 0 and entry <= 0:
            continue
        entry_due = project.close_date
        balance_due = project.payment_due_date or project.close_date
        if entry > 0:
            Installment.objects.create(
                workspace=project.workspace,
                project=project,
                due_date=entry_due,
                amount=entry,
                paid=bool(project.received_value and project.received_value >= entry),
                paid_on=entry_due if project.received_value and project.received_value >= entry else None,
            )
        balance = max(total - entry, 0)
        if balance > 0:
            full_paid = project.received_value and project.received_value >= total
            Installment.objects.create(
                workspace=project.workspace,
                project=project,
                due_date=balance_due,
                amount=balance,
                paid=bool(full_paid),
                paid_on=balance_due if full_paid else None,
            )


def remove_installments(apps, schema_editor):
    Installment = apps.get_model("studio", "ProjectInstallment")
    Installment.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('studio', '0019_project_type_specific_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProjectInstallment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('due_date', models.DateField()),
                ('amount', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('paid', models.BooleanField(default=False)),
                ('paid_on', models.DateField(blank=True, null=True)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='installments', to='studio.project')),
                ('workspace', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='studio.workspace')),
            ],
            options={
                'ordering': ['due_date', 'pk'],
            },
        ),
        migrations.RunPython(backfill_installments_from_project, remove_installments),
    ]
