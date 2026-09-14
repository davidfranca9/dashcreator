import django.db.models.deletion
from django.db import migrations, models


def copiar_produto_para_interesse(apps, schema_editor):
    """O produto de interesse virou texto livre. Os leads que ja tinham um
    infoproduto escolhido levam o nome dele pro campo novo, pra nao perder a
    informacao quando o vinculo com a tabela de produtos sair."""
    InfoLead = apps.get_model("studio", "InfoLead")
    for lead in InfoLead.objects.exclude(product=None).select_related("product"):
        if not lead.interest:
            lead.interest = lead.product.name[:160]
            lead.save(update_fields=["interest"])


def devolver_produto(apps, schema_editor):
    """Volta o vinculo quando o texto bate com o nome de um produto da conta."""
    InfoLead = apps.get_model("studio", "InfoLead")
    InfoProduct = apps.get_model("studio", "InfoProduct")
    for lead in InfoLead.objects.exclude(interest=""):
        produto = InfoProduct.objects.filter(workspace_id=lead.workspace_id, name=lead.interest).first()
        if produto:
            lead.product = produto
            lead.save(update_fields=["product"])


class Migration(migrations.Migration):

    dependencies = [
        ("studio", "0057_rotulos_crm"),
    ]

    operations = [
        migrations.AddField(
            model_name="infolead",
            name="interest",
            field=models.CharField(blank=True, default="", max_length=160),
        ),
        migrations.AddField(
            model_name="infolead",
            name="project",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="crm_leads",
                to="studio.project",
            ),
        ),
        # Copia antes de remover: a ordem importa.
        migrations.RunPython(copiar_produto_para_interesse, devolver_produto),
        migrations.RemoveField(
            model_name="infolead",
            name="product",
        ),
        migrations.AlterField(
            model_name="infolead",
            name="stage",
            field=models.CharField(
                choices=[
                    ("prospec", "Interesse"),
                    ("contato", "Primeiro Contato"),
                    ("qualif", "Qualificação"),
                    ("proposta", "Proposta Enviada"),
                    ("negoc", "Negociação"),
                    ("fechado", "Fechado"),
                    ("perdido", "Perdido"),
                ],
                db_index=True,
                default="prospec",
                max_length=20,
            ),
        ),
    ]
