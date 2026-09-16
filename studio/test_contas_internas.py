"""Recursos internos do time: quais contas entram e quais nao.

Antes so a conta da Layfe passava. Agora a do David tambem, porque as duas
sao do time e precisam enxergar o que ainda nao foi liberado pras creators.
"""

from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import InfoLead, Project
from .services import get_or_create_workspace_for_user, is_internal_account


class ContaInternaTests(TestCase):
    def conta(self, username, email=""):
        user = User.objects.create_user(username=username, password="segura123", email=email)
        return user, get_or_create_workspace_for_user(user)

    def test_layfe_e_interna(self):
        user, ws = self.conta("layfeamorim")
        self.assertTrue(is_internal_account(ws, user))

    def test_david_e_interna_pelo_usuario(self):
        user, ws = self.conta("davidfranca9")
        self.assertTrue(is_internal_account(ws, user))

    def test_email_com_o_marcador_nao_basta(self):
        """Desde 16/09/2026 só o username exato conta: email e nomes são
        editáveis pela própria creator."""
        user, ws = self.conta("dfranca", "davidfranca9@gmail.com")
        self.assertFalse(is_internal_account(ws, user))

    def test_creator_que_se_chama_layfe_amorim_no_perfil_nao_vira_interna(self):
        user = User.objects.create_user(username="marina", password="segura123", first_name="Layfe", last_name="Amorim")
        ws = get_or_create_workspace_for_user(user)
        ws.name = "Layfe Amorim"
        ws.business_full_name = "Layfe Amorim"
        ws.save()
        self.assertFalse(is_internal_account(ws, user))

    def test_username_que_so_contem_o_marcador_nao_entra(self):
        user, ws = self.conta("davidfranca9x")
        self.assertFalse(is_internal_account(ws, user))
        user2, ws2 = self.conta("layfeamorim_fake")
        self.assertFalse(is_internal_account(ws2, user2))

    def test_conta_de_equipe_do_admin_e_interna(self):
        user = User.objects.create_user(username="equipe_tcc", password="segura123", is_staff=True)
        self.assertTrue(is_internal_account(get_or_create_workspace_for_user(user), user))

    def test_sem_usuario_vale_o_dono_do_workspace(self):
        layfe, ws_layfe = self.conta("layfeamorim")
        creator, ws_creator = self.conta("aamandanegri")
        ws_creator.name = "Layfe Amorim"
        ws_creator.save()
        self.assertTrue(is_internal_account(ws_layfe))
        self.assertFalse(is_internal_account(ws_creator))

    def test_creator_comum_nao_e_interna(self):
        user, ws = self.conta("aamandanegri")
        self.assertFalse(is_internal_account(ws, user))

    def test_nome_parecido_sem_o_numero_nao_entra(self):
        """A normalizacao tira acento e junta tudo: 'David França' vira
        'davidfranca'. Sem o 9 no marcador, uma creator com esse nome entraria
        junto por acidente."""
        user, ws = self.conta("davidfranca", "davidfranca@outlook.com")
        self.assertFalse(is_internal_account(ws, user))
        user2 = User.objects.create_user(username="dsilva", password="segura123", first_name="David", last_name="França")
        ws2 = get_or_create_workspace_for_user(user2)
        self.assertFalse(is_internal_account(ws2, user2))


class AcessoInternoNasTelasTests(TestCase):
    """As quatro coisas que ficam atras do gate, vistas pelas duas contas."""

    def setUp(self):
        self.david = User.objects.create_user(username="davidfranca9", password="segura123")
        self.ws = get_or_create_workspace_for_user(self.david)
        self.creator = User.objects.create_user(username="aamandanegri", password="segura123")
        get_or_create_workspace_for_user(self.creator)

    def test_david_abre_infoprodutos(self):
        self.client.force_login(self.david)
        self.assertEqual(self.client.get(reverse("infoproducts")).status_code, 200)

    def test_david_abre_o_crm(self):
        self.client.force_login(self.david)
        self.assertEqual(self.client.get(reverse("crm")).status_code, 200)

    def test_david_abre_o_detalhe_do_trabalho(self):
        projeto = Project.objects.create(
            workspace=self.ws, company="Nivea", closing_source="Inbound",
            close_date=date.today(), due_date=date.today(),
        )
        self.client.force_login(self.david)
        self.assertEqual(self.client.get(reverse("project_detail", args=[projeto.pk])).status_code, 200)

    def test_david_ve_crm_e_infoprodutos_no_menu(self):
        self.client.force_login(self.david)
        chaves = [i["key"] for i in self.client.get(reverse("crm")).context["nav_items"]]
        self.assertIn("crm", chaves)
        self.assertIn("infoproducts", chaves)

    def test_creator_continua_sem_acesso(self):
        projeto = Project.objects.create(
            workspace=self.ws, company="Nivea", closing_source="Inbound",
            close_date=date.today(), due_date=date.today(),
        )
        self.client.force_login(self.creator)
        self.assertEqual(self.client.get(reverse("infoproducts")).status_code, 404)
        self.assertEqual(self.client.get(reverse("crm")).status_code, 404)
        self.assertEqual(self.client.get(reverse("project_detail", args=[projeto.pk])).status_code, 404)

    def test_creator_nao_ve_as_abas_no_menu(self):
        self.client.force_login(self.creator)
        chaves = [i["key"] for i in self.client.get(reverse("dashboard")).context["nav_items"]]
        self.assertNotIn("crm", chaves)
        self.assertNotIn("infoproducts", chaves)

    def test_lead_de_outra_conta_continua_bloqueado(self):
        """Acesso interno nao fura o isolamento entre workspaces."""
        outra = User.objects.create_user(username="layfeamorim", password="segura123")
        lead = InfoLead.objects.create(workspace=get_or_create_workspace_for_user(outra), name="Marina")
        self.client.force_login(self.david)
        self.assertEqual(self.client.get(reverse("crm_lead", args=[lead.pk])).status_code, 404)
