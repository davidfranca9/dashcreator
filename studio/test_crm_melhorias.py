"""Melhorias do CRM de 14/09/2026: colunas do funil, produto de interesse em
texto livre e conversao de lead fechado em trabalho."""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import InfoLead, Project, ServiceCategory
from .services import get_or_create_workspace_for_user


class CrmBase(TestCase):
    def setUp(self):
        self.layfe = User.objects.create_user(username="layfeamorim", password="segura123")
        self.ws = get_or_create_workspace_for_user(self.layfe)
        self.client.force_login(self.layfe)

    def lead(self, **extra):
        dados = {"workspace": self.ws, "name": "Studio Bela"}
        dados.update(extra)
        return InfoLead.objects.create(**dados)


class CrmColunasTests(CrmBase):
    def test_colunas_na_ordem_pedida(self):
        colunas = self.client.get(reverse("crm")).context["crm_columns"]
        self.assertEqual(
            [c["name"] for c in colunas],
            ["Interesse", "Primeiro Contato", "Qualificação", "Proposta Enviada", "Negociação", "Fechado", "Perdido"],
        )

    def test_lead_novo_entra_em_interesse(self):
        self.client.post(reverse("crm_create"), {"name": "Marina"})
        colunas = {c["name"]: c["count"] for c in self.client.get(reverse("crm")).context["crm_columns"]}
        self.assertEqual(colunas["Interesse"], 1)

    def test_primeiro_contato_recebe_card_e_registra_historico(self):
        lead = self.lead()
        resposta = self.client.post(
            reverse("crm_move", args=[lead.pk]), {"stage": "contato"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(resposta.status_code, 200)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, "contato")
        self.assertTrue(lead.events.filter(text__contains="Primeiro Contato").exists())


class CrmProdutoDeInteresseTests(CrmBase):
    def test_cadastro_salva_texto_livre(self):
        self.client.post(reverse("crm_create"), {"name": "Marina", "interest": "Conteúdo UGC"})
        self.assertEqual(InfoLead.objects.get(name="Marina").interest, "Conteúdo UGC")

    def test_formulario_tem_campo_aberto_e_nao_lista(self):
        pagina = self.client.get(reverse("crm")).content.decode()
        self.assertIn('name="interest"', pagina)
        self.assertNotIn('name="product"', pagina)

    def test_card_mostra_o_interesse(self):
        self.lead(interest="Mentoria")
        self.assertContains(self.client.get(reverse("crm")), "Mentoria")

    def test_editar_lead_atualiza_interesse(self):
        lead = self.lead(interest="Mentoria")
        self.client.post(reverse("crm_lead_update", args=[lead.pk]),
                         {"name": lead.name, "interest": "Social Media", "stage": lead.stage})
        lead.refresh_from_db()
        self.assertEqual(lead.interest, "Social Media")

    def test_mudar_etapa_pela_barra_nao_apaga_o_interesse(self):
        lead = self.lead(interest="Conteúdo UGC")
        pagina = self.client.get(reverse("crm_lead", args=[lead.pk])).content.decode()
        self.assertIn('<input type="hidden" name="interest" value="Conteúdo UGC">', pagina)
        self.client.post(reverse("crm_lead_update", args=[lead.pk]),
                         {"name": lead.name, "interest": "Conteúdo UGC", "stage": "qualif"})
        lead.refresh_from_db()
        self.assertEqual((lead.stage, lead.interest), ("qualif", "Conteúdo UGC"))

    def test_busca_encontra_pelo_interesse(self):
        self.lead(name="Ana", interest="Mentoria")
        self.lead(name="Bia", interest="Fotografia")
        colunas = self.client.get(reverse("crm"), {"q": "Mentoria"}).context["crm_columns"]
        nomes = [card["name"] for c in colunas for card in c["cards"]]
        self.assertEqual(nomes, ["Ana"])


class CrmConverterEmTrabalhoTests(CrmBase):
    def setUp(self):
        super().setUp()
        self.categoria = ServiceCategory.objects.create(workspace=self.ws, name="UGC")
        self.fechado = self.lead(stage="fechado", value=1500, whatsapp="71999990000",
                                 interest="Conteúdo UGC", note="Quer 3 vídeos")

    def payload(self):
        return {
            "company": "Studio Bela",
            "service_category": self.categoria.pk,
            "stage": "Fechado",
            "status": "Briefing",
            "total_value": "1500",
            "entry_value": "0",
            "received_value": "0",
            "deliverables_count": "3",
            "close_date": date.today().isoformat(),
            "due_date": (date.today() + timedelta(days=7)).isoformat(),
        }

    def test_botao_aparece_so_com_lead_fechado(self):
        url = reverse("crm_convert", args=[self.fechado.pk])
        self.assertContains(self.client.get(reverse("crm_lead", args=[self.fechado.pk])), url)
        aberto = self.lead(name="Ainda negociando", stage="negoc")
        self.assertNotContains(self.client.get(reverse("crm_lead", args=[aberto.pk])), "Converter em trabalho")

    def test_nao_converte_lead_que_nao_esta_fechado(self):
        aberto = self.lead(name="Ainda negociando", stage="negoc")
        resposta = self.client.get(reverse("crm_convert", args=[aberto.pk]))
        self.assertRedirects(resposta, reverse("crm_lead", args=[aberto.pk]))
        self.assertFalse(Project.objects.exists())

    def test_formulario_vem_preenchido_com_o_lead(self):
        resposta = self.client.get(reverse("crm_convert", args=[self.fechado.pk]))
        self.assertEqual(resposta.status_code, 200)
        inicial = resposta.context["form"].initial
        self.assertEqual(inicial["company"], "Studio Bela")
        self.assertEqual(inicial["received_value"], self.fechado.value)
        self.assertEqual(inicial["closing_source"], "Inbound")
        self.assertIn("Conteúdo UGC", inicial["note"])
        self.assertIn("Quer 3 vídeos", inicial["note"])

    def test_lead_de_indicacao_vira_origem_indicacao(self):
        self.fechado.origin = "Indicação"
        self.fechado.save()
        inicial = self.client.get(reverse("crm_convert", args=[self.fechado.pk])).context["form"].initial
        self.assertEqual(inicial["closing_source"], "Indicacao")

    def test_converter_cria_o_trabalho_e_liga_ao_lead(self):
        resposta = self.client.post(reverse("crm_convert", args=[self.fechado.pk]), self.payload())
        self.assertRedirects(resposta, reverse("jobs"))
        trabalho = Project.objects.get(workspace=self.ws, company="Studio Bela")
        self.fechado.refresh_from_db()
        self.assertEqual(self.fechado.project, trabalho)
        self.assertTrue(self.fechado.events.filter(text__contains="convertido em trabalho").exists())

    def test_lead_ja_convertido_leva_ao_trabalho_em_vez_de_duplicar(self):
        self.client.post(reverse("crm_convert", args=[self.fechado.pk]), self.payload())
        trabalho = Project.objects.get(workspace=self.ws, company="Studio Bela")
        resposta = self.client.get(reverse("crm_convert", args=[self.fechado.pk]))
        self.assertRedirects(resposta, reverse("project_edit", args=[trabalho.pk]), fetch_redirect_response=False)
        self.assertContains(self.client.get(reverse("crm_lead", args=[self.fechado.pk])), "Ver trabalho")
        self.assertEqual(Project.objects.filter(company="Studio Bela").count(), 1)

    def test_quadro_avisa_no_card_fechado(self):
        self.assertContains(self.client.get(reverse("crm")), "Converter em trabalho")
        self.client.post(reverse("crm_convert", args=[self.fechado.pk]), self.payload())
        self.assertContains(self.client.get(reverse("crm")), "Trabalho criado")

    def test_outra_conta_nao_converte(self):
        outra = User.objects.create_user(username="aamandanegri", password="segura123")
        get_or_create_workspace_for_user(outra)
        self.client.force_login(outra)
        self.assertEqual(self.client.get(reverse("crm_convert", args=[self.fechado.pk])).status_code, 404)
