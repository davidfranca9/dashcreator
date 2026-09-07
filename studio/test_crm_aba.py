"""Testes da separacao do CRM: ele saiu de dentro de Infoprodutos e virou
aba propria, levando os leads junto."""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import InfoLead, InfoProduct
from .services import get_or_create_workspace_for_user


class CrmAbaPropriaTests(TestCase):
    def setUp(self):
        self.layfe = User.objects.create_user(username="layfeamorim", password="segura123")
        self.ws = get_or_create_workspace_for_user(self.layfe)
        self.lead = InfoLead.objects.create(workspace=self.ws, name="Marina", value=497)
        self.client.force_login(self.layfe)

    def test_crm_tem_url_propria(self):
        resposta = self.client.get(reverse("crm"))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(reverse("crm"), "/crm/")

    def test_leads_acompanharam_o_crm(self):
        resposta = self.client.get(reverse("crm"))
        self.assertContains(resposta, "Marina")

    def test_infoprodutos_nao_mostra_mais_o_crm(self):
        resposta = self.client.get(reverse("infoproducts"))
        self.assertEqual(resposta.status_code, 200)
        self.assertNotContains(resposta, "data-crm-board")
        self.assertNotContains(resposta, "Marina")

    def test_infoprodutos_segue_mostrando_produtos(self):
        InfoProduct.objects.create(workspace=self.ws, name="Mentoria Creator", price=997)
        resposta = self.client.get(reverse("infoproducts"))
        self.assertContains(resposta, "Mentoria Creator")

    def test_menu_lista_crm_e_infoprodutos_separados(self):
        resposta = self.client.get(reverse("crm"))
        chaves = [item["key"] for item in resposta.context["nav_items"]]
        self.assertIn("crm", chaves)
        self.assertIn("infoproducts", chaves)

    def test_menu_marca_o_crm_como_pagina_atual(self):
        resposta = self.client.get(reverse("crm"))
        atual = [item["key"] for item in resposta.context["nav_items"] if item["active"]]
        self.assertEqual(atual, ["crm"])

    def test_pagina_do_lead_volta_pro_crm(self):
        resposta = self.client.get(reverse("crm_lead", args=[self.lead.pk]))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'href="/crm/"')

    def test_mover_lead_usa_a_url_nova(self):
        self.client.post(reverse("crm_move", args=[self.lead.pk]), {"stage": "negoc"})
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, "negoc")


class CrmEtapasTests(TestCase):
    """Os rotulos das colunas estavam trocados em relacao aos ids gravados:
    'proposta' aparecia como Negociacao e 'negoc' como Recuperacao, que nem e'
    conceito de CRM. O historico do lead registrava o nome errado."""

    def setUp(self):
        self.layfe = User.objects.create_user(username="layfeamorim", password="segura123")
        self.ws = get_or_create_workspace_for_user(self.layfe)
        self.lead = InfoLead.objects.create(workspace=self.ws, name="Marina", value=497)
        self.client.force_login(self.layfe)

    def test_colunas_na_ordem_de_um_funil_de_venda(self):
        colunas = self.client.get(reverse("crm")).context["crm_columns"]
        self.assertEqual(
            [(c["id"], c["name"]) for c in colunas],
            [
                ("prospec", "Interessadas"),
                ("qualif", "Qualificadas"),
                ("proposta", "Proposta enviada"),
                ("negoc", "Negociação"),
                ("fechado", "Fechado"),
                ("perdido", "Perdido"),
            ],
        )

    def test_historico_registra_o_nome_certo_da_etapa(self):
        self.client.post(reverse("crm_move", args=[self.lead.pk]), {"stage": "negoc"})
        self.assertTrue(self.lead.events.filter(text__contains="Negociação").exists())
        self.assertFalse(self.lead.events.filter(text__contains="Recuperação").exists())

    def test_recuperacao_nao_e_etapa_de_crm(self):
        """Recuperação é conceito da Prospecção, não do CRM."""
        resposta = self.client.get(reverse("crm"))
        nomes = [c["name"] for c in resposta.context["crm_columns"]]
        self.assertNotIn("Recuperação", nomes)
