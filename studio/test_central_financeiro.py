from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from studio.models import CentralFinanceEntry
from studio.services import get_or_create_workspace_for_user


SENHA = "SenhaForte123!"


@override_settings(CENTRAL_ACESSO_DIRETO=True)
class CentralFinanceiroTests(TestCase):
    def setUp(self):
        self.layfe = get_user_model().objects.create_user(
            "layfeamorim", email="layfe@example.com", password=SENHA
        )
        get_or_create_workspace_for_user(self.layfe)
        self.client.post("/central/entrar/", {"username": "layfe@example.com", "password": SENHA})

    def test_comeca_zerado(self):
        resposta = self.client.get("/central/")
        self.assertContains(resposta, "Caixa zerado")
        self.assertEqual(resposta.context["financeiro"]["saldo"], "R$ 0,00")

    def test_lanca_por_produto_e_calcula_fluxo(self):
        for kind, product, amount in (
            ("income", "Creator Day Experience", "1.200,00"),
            ("expense", "Creator Day Experience", "200,00"),
            ("fixed", "Creator Day Experience", "100,00"),
            ("income", "Dash Creator", "279,80"),
        ):
            resposta = self.client.post("/central/financeiro/salvar/", {
                "kind": kind, "product": product, "amount": amount,
                "description": "Teste", "occurred_on": "2026-10-08",
            })
            self.assertRedirects(resposta, "/central/#financeiro", fetch_redirect_response=False)

        dados = self.client.get("/central/").context["financeiro"]
        self.assertEqual(dados["entradas"], "R$ 1.479,80")
        self.assertEqual(dados["saidas"], "R$ 200,00")
        self.assertEqual(dados["fixos"], "R$ 100,00")
        self.assertEqual(dados["saldo"], "R$ 1.179,80")
        creator_day = next(p for p in dados["por_produto"] if p["nome"] == "Creator Day Experience")
        self.assertEqual(creator_day["saldo_txt"], "R$ 900,00")

    def test_exclui_lancamento(self):
        movimento = CentralFinanceEntry.objects.create(
            kind="income", product="Planner", amount=Decimal("157"), occurred_on="2026-10-08"
        )
        self.client.post(f"/central/financeiro/{movimento.pk}/excluir/")
        self.assertFalse(CentralFinanceEntry.objects.exists())

