from django.db import migrations


def backfill_project_funnel(apps, schema_editor):
    """Reassocia projetos com funnel_id=None ao primeiro funil do workspace.
    Cobre projetos criados entre 0039 (seed inicial) e a hora em que o form
    passou a setar o funnel automaticamente."""
    Project = apps.get_model("studio", "Project")
    Funnel = apps.get_model("studio", "Funnel")

    for project in Project.objects.filter(funnel__isnull=True):
        default_funnel = (
            Funnel.objects.filter(workspace=project.workspace)
            .order_by("position", "name")
            .first()
        )
        if default_funnel:
            project.funnel = default_funnel
            project.save(update_fields=["funnel"])


def undo(apps, schema_editor):
    # Nao desfaz o backfill: seria arbitrario decidir quais projetos "voltar"
    # pra funnel=None. Mantem tudo associado.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("studio", "0042_seed_default_emojis"),
    ]

    operations = [
        migrations.RunPython(backfill_project_funnel, undo),
    ]
