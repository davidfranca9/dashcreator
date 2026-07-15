from django.db import migrations


DEFAULT_COLUMNS = [
    "Briefing",
    "Em produção",
    "Aguardando aprovação",
    "Concluído",
    "Cancelado",
]


def seed_default_funnels(apps, schema_editor):
    Workspace = apps.get_model("studio", "Workspace")
    Funnel = apps.get_model("studio", "Funnel")
    FunnelColumn = apps.get_model("studio", "FunnelColumn")
    Project = apps.get_model("studio", "Project")

    for workspace in Workspace.objects.all():
        funnel, _ = Funnel.objects.get_or_create(
            workspace=workspace,
            name="Padrão",
            defaults={"description": "Fluxo padrão de trabalhos.", "position": 0},
        )
        # Cria as 5 colunas iniciais caso o funil ainda não tenha nenhuma.
        if not funnel.columns.exists():
            for idx, col_name in enumerate(DEFAULT_COLUMNS):
                FunnelColumn.objects.create(funnel=funnel, name=col_name, position=idx)
        # Associa todos os projetos do workspace sem funil ao padrão.
        Project.objects.filter(workspace=workspace, funnel__isnull=True).update(
            funnel=funnel
        )


def undo_seed(apps, schema_editor):
    # Desassocia projetos e apaga os funis "Padrão" criados. As colunas caem em
    # cascata via on_delete=CASCADE.
    Project = apps.get_model("studio", "Project")
    Funnel = apps.get_model("studio", "Funnel")
    Project.objects.filter(funnel__name="Padrão").update(funnel=None)
    Funnel.objects.filter(name="Padrão").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("studio", "0038_alter_project_status_funnel_project_funnel_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_default_funnels, undo_seed),
    ]
