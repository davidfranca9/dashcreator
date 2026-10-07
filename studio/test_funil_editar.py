"""Renomear e excluir funil no Trabalhos."""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Funnel, FunnelColumn, Project, ServiceCategory
from .services import get_or_create_workspace_for_user

SENHA = "SenhaForte123!"


class FunilEditarTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("creator", email="creator@example.com", password=SENHA)
        self.ws = get_or_create_workspace_for_user(self.user)
        self.categoria = ServiceCategory.objects.create(workspace=self.ws, name="UGC")
        self.padrao = Funnel.objects.create(workspace=self.ws, name="Padrão", position=0)
        for i, nome in enumerate(("Briefing", "Em produção", "Concluído")):
            FunnelColumn.objects.create(funnel=self.padrao, name=nome, position=i)
        self.errado = Funnel.objects.create(workspace=self.ws, name="Aguardando produto 📦", position=1)
        FunnelColumn.objects.create(funnel=self.errado, name="Nova coluna", position=0)
        self.client.force_login(self.user)

    def trabalho(self, funnel, status, empresa="Marca"):
        return Project.objects.create(
            workspace=self.ws, company=empresa, service_category=self.categoria, funnel=funnel,
            status=status, deliverables_count=1, total_value=Decimal("100"), entry_value=Decimal("0"),
            close_date=date(2026, 10, 1), due_date=date(2026, 10, 20),
        )

    def test_renomeia_o_funil(self):
        r = self.client.post(reverse("funnel_update", args=[self.errado.pk]), {"name": "  Parcerias  "})
        self.assertEqual(r.json(), {"ok": True, "name": "Parcerias"})
        self.errado.refresh_from_db()
        self.assertEqual(self.errado.name, "Parcerias")

    def test_nome_vazio_ou_repetido_nao_salva(self):
        vazio = self.client.post(reverse("funnel_update", args=[self.errado.pk]), {"name": "   "})
        self.assertEqual(vazio.status_code, 400)
        repetido = self.client.post(reverse("funnel_update", args=[self.errado.pk]), {"name": "Padrão"})
        self.assertEqual(repetido.status_code, 400)
        self.assertIn("Já existe", repetido.json()["error"])
        self.errado.refresh_from_db()
        self.assertEqual(self.errado.name, "Aguardando produto 📦")

    def test_exclui_funil_vazio(self):
        r = self.client.post(reverse("funnel_delete", args=[self.errado.pk]))
        self.assertEqual(r.json(), {"ok": True, "moved": 0, "destino": "Padrão"})
        self.assertFalse(Funnel.objects.filter(pk=self.errado.pk).exists())
        self.assertFalse(FunnelColumn.objects.filter(funnel_id=self.errado.pk).exists())

    def test_trabalhos_vao_para_o_outro_funil(self):
        FunnelColumn.objects.create(funnel=self.errado, name="Briefing", position=1)
        mantem = self.trabalho(self.errado, "Briefing", "Marca A")
        muda = self.trabalho(self.errado, "Nova coluna", "Marca B")
        r = self.client.post(reverse("funnel_delete", args=[self.errado.pk]))
        self.assertEqual(r.json()["moved"], 2)
        mantem.refresh_from_db()
        muda.refresh_from_db()
        self.assertEqual((mantem.funnel, mantem.status), (self.padrao, "Briefing"))
        self.assertEqual((muda.funnel, muda.status), (self.padrao, "Briefing"))
        self.assertEqual(Project.objects.filter(workspace=self.ws).count(), 2)

    def test_nao_deixa_ficar_sem_funil(self):
        self.client.post(reverse("funnel_delete", args=[self.errado.pk]))
        r = self.client.post(reverse("funnel_delete", args=[self.padrao.pk]))
        self.assertEqual(r.status_code, 400)
        self.assertIn("pelo menos um funil", r.json()["error"])
        self.assertTrue(Funnel.objects.filter(pk=self.padrao.pk).exists())

    def test_funil_de_outra_pessoa_nao_pode_ser_mexido(self):
        outra = get_user_model().objects.create_user("outra", email="outra@example.com", password=SENHA)
        ws_outra = get_or_create_workspace_for_user(outra)
        alheio = Funnel.objects.create(workspace=ws_outra, name="Padrão", position=0)
        FunnelColumn.objects.create(funnel=alheio, name="Briefing", position=0)
        self.assertEqual(self.client.post(reverse("funnel_update", args=[alheio.pk]), {"name": "X"}).status_code, 404)
        self.assertEqual(self.client.post(reverse("funnel_delete", args=[alheio.pk])).status_code, 404)
        self.assertTrue(Funnel.objects.filter(pk=alheio.pk, name="Padrão").exists())

    def test_so_aceita_post(self):
        self.assertEqual(self.client.get(reverse("funnel_update", args=[self.errado.pk])).status_code, 405)
        self.assertEqual(self.client.get(reverse("funnel_delete", args=[self.errado.pk])).status_code, 405)

    def test_tela_mostra_os_botoes_de_renomear_e_excluir(self):
        pagina = self.client.get(reverse("jobs"))
        self.assertContains(pagina, f'data-funnel-rename="{self.errado.pk}"')
        self.assertContains(pagina, f'data-funnel-delete="{self.errado.pk}"')
        self.assertNotContains(pagina, "—")
