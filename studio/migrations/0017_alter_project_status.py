# Migra os 7 status antigos para os 5 status novos do brief Dash Creator
# (Briefing, Em produção, Aguardando aprovação, Concluído, Cancelado).

from django.db import migrations, models


STATUS_FORWARD_MAP = {
    "Aguardando produto": "Em produção",
    "Em gravacao": "Em produção",
    "Em edicao": "Em produção",
    "Aguardando cliente": "Aguardando aprovação",
    "Aprovado": "Concluído",
    "Entregue": "Concluído",
}

STATUS_BACKWARD_MAP = {
    "Em produção": "Aguardando produto",
    "Aguardando aprovação": "Aguardando cliente",
    "Concluído": "Entregue",
    "Cancelado": "Briefing",
}


def map_existing_status_forward(apps, schema_editor):
    Project = apps.get_model("studio", "Project")
    for old_value, new_value in STATUS_FORWARD_MAP.items():
        Project.objects.filter(status=old_value).update(status=new_value)


def map_existing_status_backward(apps, schema_editor):
    Project = apps.get_model("studio", "Project")
    for old_value, new_value in STATUS_BACKWARD_MAP.items():
        Project.objects.filter(status=old_value).update(status=new_value)


class Migration(migrations.Migration):

    dependencies = [
        ("studio", "0016_alter_prospect_stage"),
    ]

    operations = [
        migrations.RunPython(map_existing_status_forward, map_existing_status_backward),
        migrations.AlterField(
            model_name="project",
            name="status",
            field=models.CharField(
                choices=[
                    ("Briefing", "Briefing"),
                    ("Em produção", "Em produção"),
                    ("Aguardando aprovação", "Aguardando aprovação"),
                    ("Concluído", "Concluído"),
                    ("Cancelado", "Cancelado"),
                ],
                default="Briefing",
                max_length=40,
            ),
        ),
    ]
