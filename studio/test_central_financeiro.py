from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from studio.models import CentralFinanceEntry, Purchase
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

    def test_checkout_aprovado_entra_automaticamente_sem_duplicar(self):
        base = {
            "product_key": "creatorday", "product_name": "Creator Day Experience",
            "customer_name": "Ana", "customer_email": "ana@example.com", "amount": Decimal("120"),
        }
        Purchase.objects.create(**base, status=Purchase.STATUS_APPROVED)
        Purchase.objects.create(**{**base, "customer_email": "bia@example.com"}, status=Purchase.STATUS_PENDING)

        dados = self.client.get("/central/").context["financeiro"]
        self.assertEqual(dados["entradas"], "R$ 120,00")
        self.assertEqual(dados["automaticos"], 1)
        self.assertEqual(dados["manuais"], 0)
        self.assertEqual(dados["total"], 1)
        self.assertTrue(dados["movimentos"][0]["automatico"])

        # Reabrir a Central só relê a compra: não cria lançamento paralelo.
        self.client.get("/central/")
        self.assertFalse(CentralFinanceEntry.objects.exists())


@override_settings(CENTRAL_ACESSO_DIRETO=True)
class CentralReembolsoTests(TestCase):
    def setUp(self):
        self.layfe = get_user_model().objects.create_user(
            "layfeamorim", email="layfe@example.com", password=SENHA
        )
        get_or_create_workspace_for_user(self.layfe)
        self.client.post("/central/entrar/", {"username": "layfe@example.com", "password": SENHA})
        self.compra = Purchase.objects.create(
            product_key="creatorday", product_name="Creator Day Experience",
            customer_name="Ana", customer_email="ana@example.com",
            amount=Decimal("120"), status=Purchase.STATUS_APPROVED,
        )

    def test_reembolso_sai_das_entradas_e_volta_ao_desfazer(self):
        resposta = self.client.post(f"/central/financeiro/compra/{self.compra.pk}/reembolsar/")
        self.assertRedirects(resposta, "/central/#financeiro", fetch_redirect_response=False)
        self.compra.refresh_from_db()
        self.assertEqual(self.compra.status, Purchase.STATUS_REFUNDED)
        self.assertIsNotNone(self.compra.refunded_at)

        dados = self.client.get("/central/").context["financeiro"]
        self.assertEqual(dados["entradas"], "R$ 0,00")
        self.assertEqual(dados["saidas"], "R$ 0,00")
        self.assertEqual(dados["saldo"], "R$ 0,00")
        self.assertEqual(dados["reembolsado"], "R$ 120,00")
        self.assertEqual(dados["reembolsadas"], 1)
        self.assertEqual(dados["automaticos"], 0)
        self.assertTrue(dados["movimentos"][0]["reembolsada"])
        self.assertEqual(dados["por_produto"][0]["entradas_txt"], "R$ 0,00")

        # o mesmo botão desfaz
        self.client.post(f"/central/financeiro/compra/{self.compra.pk}/reembolsar/")
        self.compra.refresh_from_db()
        self.assertEqual(self.compra.status, Purchase.STATUS_APPROVED)
        self.assertIsNone(self.compra.refunded_at)
        self.assertEqual(self.client.get("/central/").context["financeiro"]["entradas"], "R$ 120,00")

    def test_reembolso_tira_do_creator_day_e_da_lista_de_presenca(self):
        self.client.post(f"/central/financeiro/compra/{self.compra.pk}/reembolsar/")
        contexto = self.client.get("/central/").context
        self.assertEqual(contexto["checkout"]["creatorday"]["pagas"], 0)
        self.assertEqual(contexto["checkout"]["creatorday"]["reembolsadas"], 1)
        self.assertEqual(contexto["evento"]["presenca"]["pagos_total"], 0)

    def test_so_o_time_reembolsa(self):
        self.client.post("/central/sair/")
        resposta = self.client.post(f"/central/financeiro/compra/{self.compra.pk}/reembolsar/")
        self.assertNotEqual(resposta.status_code, 200)
        self.compra.refresh_from_db()
        self.assertEqual(self.compra.status, Purchase.STATUS_APPROVED)

    def test_pendente_nao_pode_ser_reembolsada(self):
        pendente = Purchase.objects.create(
            product_key="creatorday", product_name="Creator Day Experience",
            customer_name="Bia", customer_email="bia@example.com",
            amount=Decimal("120"), status=Purchase.STATUS_PENDING,
        )
        self.client.post(f"/central/financeiro/compra/{pendente.pk}/reembolsar/")
        pendente.refresh_from_db()
        self.assertEqual(pendente.status, Purchase.STATUS_PENDING)
