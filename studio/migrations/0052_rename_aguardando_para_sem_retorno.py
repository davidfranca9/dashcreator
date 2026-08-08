from django.db import migrations


def rename_forward(apps, schema_editor):
    """Renomeia 'Aguardando retorno' -> 'Sem Retorno' em todos os prospects
    ativos. Idempotente."""
    Prospect = apps.get_model("studio", "Prospect")
    Prospect.objects.filter(stage="Aguardando retorno").update(stage="Sem Retorno")


def rename_backward(apps, schema_editor):
    """Rollback: 'Sem Retorno' -> 'Aguardando retorno'. Serve apenas se voltar
    a migration anterior."""
    Prospect = apps.get_model("studio", "Prospect")
    Prospect.objects.filter(stage="Sem Retorno").update(stage="Aguardando retorno")


class Migration(migrations.Migration):

    dependencies = [
        ("studio", "0051_alter_prospect_stage"),
    ]

    operations = [
        migrations.RunPython(rename_forward, rename_backward),
    ]
