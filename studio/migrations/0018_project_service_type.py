# Adiciona service_type (enum dos 11 tipos do brief Dash Creator) ao Project
# e classifica os projetos existentes por heurística sobre o nome da
# ServiceCategory associada. ServiceCategory continua existindo como rótulo
# livre opcional; service_type é o que dirige o form e os relatórios por tipo.

from django.db import migrations, models


HEURISTIC_RULES = [
    ("ugc_creator", ("ugc creator", "ugc-creator", "ugc")),
    ("social_media", ("social media", "social-media", "redes sociais", "smm")),
    ("ugc_manager", ("ugc manager", "gerencia de creators", "manager", "gerenciamento")),
    ("consultoria_marketing", ("consultoria de marketing", "consultoria", "consultor")),
    ("storymaker", ("storymaker", "story maker", "stories")),
    ("editora_video", ("editora de video", "edicao de video", "edicao", "editor")),
    ("videomaker", ("videomaker", "video maker", "filmmaker", "captacao")),
    ("publicidade", ("publicidade", "publi", "anuncio", "ads")),
    ("shop_creator", ("shop creator", "shop", "loja")),
    ("afiliacao", ("afiliacao", "afiliação", "comissao", "comissão", "afiliado")),
    ("freelancer", ("freelancer", "freela")),
]


def _normalize(value: str) -> str:
    import unicodedata

    decomposed = unicodedata.normalize("NFKD", value or "")
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii")
    return ascii_only.lower().strip()


def classify_existing_projects(apps, schema_editor):
    Project = apps.get_model("studio", "Project")
    for project in Project.objects.select_related("service_category").iterator():
        category_name = project.service_category.name if project.service_category_id else ""
        normalized = _normalize(category_name)
        match = "outros"
        if normalized:
            for service_type, needles in HEURISTIC_RULES:
                if any(needle in normalized for needle in needles):
                    match = service_type
                    break
        if project.service_type != match:
            project.service_type = match
            project.save(update_fields=["service_type", "updated_at"])


def reset_service_type(apps, schema_editor):
    Project = apps.get_model("studio", "Project")
    Project.objects.update(service_type="outros")


class Migration(migrations.Migration):

    dependencies = [
        ("studio", "0017_alter_project_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="service_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("ugc_creator", "UGC Creator"),
                    ("freelancer", "Freelancer"),
                    ("editora_video", "Editora de Vídeo"),
                    ("videomaker", "Videomaker"),
                    ("storymaker", "Storymaker"),
                    ("social_media", "Social Media"),
                    ("ugc_manager", "UGC Manager"),
                    ("consultoria_marketing", "Consultoria de Marketing"),
                    ("publicidade", "Publicidade"),
                    ("shop_creator", "Shop Creator"),
                    ("afiliacao", "Afiliação / Comissão"),
                    ("outros", "Outros"),
                ],
                default="outros",
                max_length=40,
            ),
        ),
        migrations.RunPython(classify_existing_projects, reset_service_type),
    ]
