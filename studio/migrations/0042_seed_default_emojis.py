from django.db import migrations


DEFAULT_EMOJIS = {
    "Briefing": "📝",
    "Em produção": "🎬",
    "Aguardando aprovação": "👀",
    "Concluído": "✅",
    "Cancelado": "❌",
}


def seed_emojis(apps, schema_editor):
    FunnelColumn = apps.get_model("studio", "FunnelColumn")
    for name, emoji in DEFAULT_EMOJIS.items():
        FunnelColumn.objects.filter(name=name, emoji="").update(emoji=emoji)


def undo(apps, schema_editor):
    FunnelColumn = apps.get_model("studio", "FunnelColumn")
    FunnelColumn.objects.filter(name__in=DEFAULT_EMOJIS.keys()).update(emoji="")


class Migration(migrations.Migration):

    dependencies = [
        ("studio", "0041_funnelcolumn_emoji"),
    ]

    operations = [
        migrations.RunPython(seed_emojis, undo),
    ]
