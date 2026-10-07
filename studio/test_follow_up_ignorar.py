"""Botão Ignorar da Prospecção: a lista de marcas ignoradas cresce sem estourar.

Em 07/10/2026 o Dash dava erro 500 ao clicar em Ignorar: a lista ia para um campo
de 255 caracteres e o Postgres recusa o que passa disso (o SQLite dos testes, não).
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Niche, Project, ServiceCategory, WorkspaceSetting
from .services import FOLLOW_UP_DISMISSED_COMPANIES_KEY, dismiss_follow_up_company, follow_up_state
from .services import get_or_create_workspace_for_user

SENHA = "SenhaForte123!"


class IgnorarFollowUpTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("creator", email="creator@example.com", password=SENHA)
        self.ws = get_or_create_workspace_for_user(self.user)
        self.niche = Niche.objects.create(workspace=self.ws, name="Moda")
        self.categoria = ServiceCategory.objects.create(workspace=self.ws, name="UGC")
        self.client.force_login(self.user)

    def entregue(self, empresa):
        return Project.objects.create(
            workspace=self.ws, company=empresa, niche=self.niche, service_category=self.categoria,
            stage="Entregue", status="Concluído", total_value=1000, entry_value=500, received_value=1000,
            deliverables_count=1, progress=100,
            close_date=date.today() - timedelta(days=60), due_date=date.today() - timedelta(days=45),
        )

    def test_campo_das_configuracoes_nao_tem_limite_curto(self):
        # trava a regressão: com max_length=255 o Postgres derruba o Ignorar
        self.assertIsNone(WorkspaceSetting._meta.get_field("value").max_length)

    def test_ignorar_muitas_marcas_guarda_todas(self):
        marcas = [f"Marca Parceira Numero {i:02d} LTDA" for i in range(30)]
        for marca in marcas:
            self.entregue(marca)
            resposta = self.client.post(reverse("follow_up_dismiss"), {"company_key": marca})
            self.assertEqual(resposta.status_code, 302)

        _, ignoradas = follow_up_state(self.ws)
        self.assertEqual(len(ignoradas), 30)
        guardado = WorkspaceSetting.objects.get(workspace=self.ws, key=FOLLOW_UP_DISMISSED_COMPANIES_KEY)
        self.assertGreater(len(guardado.value), 255, "o teste precisa passar do limite antigo para valer")

    def test_marca_ignorada_some_do_follow_up(self):
        self.entregue("Reserva")
        self.client.post(reverse("follow_up_dismiss"), {"company_key": "reserva"})
        pagina = self.client.get(reverse("prospection"))
        self.assertEqual(pagina.status_code, 200)
        self.assertEqual(pagina.context["follow_up_alerts"], [])

    def test_prospeccao_abre_com_a_lista_grande(self):
        for i in range(30):
            dismiss_follow_up_company(self.ws, f"Marca Parceira Numero {i:02d} LTDA")
        pagina = self.client.get(reverse("prospection"))
        self.assertEqual(pagina.status_code, 200)

    def test_chave_vazia_nao_quebra(self):
        resposta = self.client.post(reverse("follow_up_dismiss"), {"company_key": "   "})
        self.assertEqual(resposta.status_code, 302)
        _, ignoradas = follow_up_state(self.ws)
        self.assertEqual(ignoradas, set())
