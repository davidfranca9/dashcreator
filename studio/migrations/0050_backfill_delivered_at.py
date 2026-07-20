from django.db import migrations


def backfill(apps, schema_editor):
    """Preenche delivered_at para projetos ja Entregues sem valor. Usa
    updated_at como melhor proxy da data de conclusao (nao existia campo
    antes). Novos deliveries setam delivered_at via view project_mark_delivered."""
    Project = apps.get_model("studio", "Project")
    for p in Project.objects.filter(stage="Entregue", delivered_at__isnull=True):
        Project.objects.filter(pk=p.pk).update(delivered_at=p.updated_at.date())


def undo(apps, schema_editor):
    pass  # noop


class Migration(migrations.Migration):

    dependencies = [
        ("studio", "0049_project_delivered_at"),
    ]

    operations = [
        migrations.RunPython(backfill, undo),
    ]
