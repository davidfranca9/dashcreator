from django.db import migrations

# "Prospeccao" era a etapa de quem ja recebeu a abordagem: vira
# "Primeiro Contato". "Sem Retorno" era o fim da linha antes do arquivo:
# vira "Recuperacao", que no desenho novo e' uma etapa comercial ativa, nao
# um descarte. "Follow-up", "Rascunho", "Negociacao" e "Fechado" seguem
# iguais, e as etapas novas (Qualificacao, Proposta) nascem vazias.
RENOMEACOES = [
    ("Prospeccao", "Primeiro Contato"),
    ("Sem Retorno", "Recuperacao"),
]


def renomear(apps, schema_editor):
    Prospect = apps.get_model("studio", "Prospect")
    for antigo, novo in RENOMEACOES:
        Prospect.objects.filter(stage=antigo).update(stage=novo)


def desfazer(apps, schema_editor):
    Prospect = apps.get_model("studio", "Prospect")
    for antigo, novo in RENOMEACOES:
        Prospect.objects.filter(stage=novo).update(stage=antigo)


def marcar_entrada_na_etapa(apps, schema_editor):
    """stage_changed_at nasce vazio, e sem ele todo card apareceria como
    'parado ha 0 dias'. Usa a ultima atividade conhecida como ponto de
    partida, que e' a melhor aproximacao que existe pro dado antigo."""
    Prospect = apps.get_model("studio", "Prospect")
    for item in Prospect.objects.filter(stage_changed_at__isnull=True):
        item.stage_changed_at = item.last_activity_at or item.updated_at or item.created_at
        item.save(update_fields=["stage_changed_at"])


def limpar_entrada_na_etapa(apps, schema_editor):
    Prospect = apps.get_model("studio", "Prospect")
    Prospect.objects.update(stage_changed_at=None)


class Migration(migrations.Migration):

    dependencies = [
        ("studio", "0055_campos_prospeccao"),
    ]

    operations = [
        migrations.RunPython(renomear, desfazer),
        migrations.RunPython(marcar_entrada_na_etapa, limpar_entrada_na_etapa),
    ]
