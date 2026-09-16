"""Checkout do Creator Day Experience: ingresso de evento, sem código do Dash."""
import json
from decimal import Decimal
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from .checkout import get_product
from .checkout_views import _approve_purchase
from .models import AccessCode, Purchase


def _compra(**extra):
    dados = {
        "product_key": "creatorday",
        "product_name": "Creator Day Experience",
        "amount": Decimal("120.00"),
        "customer_name": "Maria",
        "customer_email": "maria@example.com",
        "customer_cpf": "12345678909",
    }
    dados.update(extra)
    return Purchase.objects.create(**dados)


def _sdk_de_pagamento(resposta):
    class FakePaymentApi:
        def create(self, payload, request_options):
            return {"status": 201, "response": resposta}

    class FakeSdk:
        def payment(self):
            return FakePaymentApi()

    return FakeSdk()


@override_settings(MERCADO_PAGO_PUBLIC_KEY="TEST-public-key", MERCADO_PAGO_ACCESS_TOKEN="TEST-access-token")
class CheckoutCreatorDayTest(TestCase):
    def test_produto_e_ingresso_de_120_reais(self):
        produto = get_product("creatorday")
        self.assertEqual(produto.price, Decimal("120.00"))
        self.assertTrue(produto.is_ticket)
        self.assertEqual(produto.success_path, "/checkout/creator-day/sucesso/")
        self.assertEqual(produto.failure_path, "/checkout/creator-day/erro/")
        self.assertFalse(get_product("dashcreator").is_ticket)

    def test_pagina_do_app_volta_para_o_sucesso_do_creator_day(self):
        response = self.client.get(reverse("checkout_page", kwargs={"product_key": "creatorday"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Creator Day Experience")
        self.assertContains(response, "R$ 120,00")
        self.assertEqual(
            response.context["success_url"],
            "https://thecreatorsclub.com.br/checkout/creator-day/sucesso/",
        )

    def test_preferencia_cobra_120_e_volta_para_as_paginas_do_evento(self):
        enviado = {}

        class FakePreferenceApi:
            def create(self, payload):
                enviado.update(payload)
                return {"status": 201, "response": {"id": "pref_cd"}}

        class FakeSdk:
            def preference(self):
                return FakePreferenceApi()

        with patch("studio.checkout_views._mp_sdk", return_value=FakeSdk()):
            response = self.client.post(
                reverse("checkout_preference"),
                data=json.dumps({
                    "product_key": "creatorday",
                    "customer_name": "Maria",
                    "customer_email": "maria@example.com",
                    "customer_cpf": "123.456.789-09",
                    "customer_phone": "(71) 99999-0000",
                }),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["amount"], 120.0)
        compra = Purchase.objects.get(customer_email="maria@example.com")
        self.assertEqual(compra.product_key, "creatorday")
        self.assertEqual(compra.customer_phone, "(71) 99999-0000")
        self.assertEqual(enviado["items"][0]["unit_price"], 120.0)
        self.assertEqual(
            enviado["back_urls"]["success"],
            f"https://thecreatorsclub.com.br/checkout/creator-day/sucesso/?p={compra.pk}",
        )
        self.assertEqual(
            enviado["back_urls"]["failure"],
            f"https://thecreatorsclub.com.br/checkout/creator-day/erro/?p={compra.pk}",
        )

    def test_aprovar_ingresso_nao_gera_codigo_e_manda_email_do_ingresso(self):
        compra = _compra()

        _approve_purchase(compra, {
            "id": "pay_cd",
            "payment_method_id": "pix",
            "date_approved": "2026-10-01T12:00:00.000-03:00",
        })

        compra.refresh_from_db()
        self.assertEqual(compra.status, Purchase.STATUS_APPROVED)
        self.assertIsNone(compra.access_code)
        self.assertEqual(compra.mp_payment_id, "pay_cd")
        self.assertEqual(compra.payment_method, "pix")
        self.assertIsNotNone(compra.paid_at)
        self.assertIsNotNone(compra.notified_at)
        self.assertEqual(AccessCode.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["maria@example.com"])
        self.assertEqual(email.subject, "Seu ingresso do Creator Day Experience está confirmado")
        self.assertIn("Data: 17 de outubro de 2026, às 14h", email.body)
        self.assertIn("Local: Piatã, Salvador/BA", email.body)
        self.assertIn(f"Número do pedido: {compra.pk}", email.body)
        self.assertNotIn("código de acesso", email.body)
        self.assertNotIn(reverse("signup"), email.body)
        self.assertNotIn("—", email.body + email.subject)

    def test_aprovacao_repetida_manda_um_email_so(self):
        compra = _compra()
        _approve_purchase(compra, {"id": "pay_cd", "payment_method_id": "pix"})
        _approve_purchase(compra, {"id": "pay_cd", "payment_method_id": "pix"})
        Purchase.objects.get(pk=compra.pk)  # continua existindo
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(AccessCode.objects.count(), 0)

    def test_status_fica_pronto_quando_o_ingresso_e_aprovado(self):
        compra = _compra(status=Purchase.STATUS_APPROVED)
        response = self.client.get(reverse("checkout_status"), {"purchase_id": compra.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "approved")
        self.assertTrue(response.json()["access_ready"])

    def test_status_pendente_nao_esta_pronto(self):
        compra = _compra()
        with self.settings(MERCADO_PAGO_ACCESS_TOKEN=""):
            response = self.client.get(reverse("checkout_status"), {"purchase_id": compra.pk})
        self.assertFalse(response.json()["access_ready"])

    def test_pagamento_aprovado_no_brick_confirma_o_ingresso(self):
        compra = _compra()
        sdk = _sdk_de_pagamento({
            "id": "pay_card",
            "status": "approved",
            "payment_method_id": "master",
            "date_approved": "2026-10-01T12:00:00.000-03:00",
        })
        with patch("studio.checkout_views._mp_sdk", return_value=sdk), patch(
            "studio.checkout_views._mp_request_options", return_value=object()
        ):
            response = self.client.post(
                reverse("checkout_payment"),
                data=json.dumps({
                    "purchase_id": compra.pk,
                    "form_data": {
                        "transaction_amount": 120,
                        "payment_method_id": "master",
                        "installments": 12,
                        "token": "tok",
                        "payer": {"email": "maria@example.com"},
                    },
                }),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["purchase_status"], "approved")
        compra.refresh_from_db()
        self.assertEqual(compra.status, Purchase.STATUS_APPROVED)
        self.assertIsNone(compra.access_code)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("ingresso", mail.outbox[0].subject)

    def test_pix_pendente_nao_confirma_nem_manda_email(self):
        compra = _compra()
        sdk = _sdk_de_pagamento({
            "id": "pay_pix",
            "status": "pending",
            "payment_method_id": "pix",
            "point_of_interaction": {"transaction_data": {"qr_code": "000201pix"}},
        })
        with patch("studio.checkout_views._mp_sdk", return_value=sdk), patch(
            "studio.checkout_views._mp_request_options", return_value=object()
        ):
            response = self.client.post(
                reverse("checkout_payment"),
                data=json.dumps({
                    "purchase_id": compra.pk,
                    "form_data": {"transaction_amount": 120, "payment_method_id": "pix"},
                }),
                content_type="application/json",
            )

        self.assertEqual(response.json()["pix"]["qr_code"], "000201pix")
        compra.refresh_from_db()
        self.assertEqual(compra.status, Purchase.STATUS_PENDING)
        self.assertEqual(len(mail.outbox), 0)

    def test_ingresso_ja_aprovado_nao_cobra_de_novo(self):
        compra = _compra(status=Purchase.STATUS_APPROVED, mp_payment_id="pay_antigo")

        class SdkQueNaoPodeSerChamado:
            def payment(self):
                raise AssertionError("não devia chamar o Mercado Pago de novo")

        with patch("studio.checkout_views._mp_sdk", return_value=SdkQueNaoPodeSerChamado()):
            response = self.client.post(
                reverse("checkout_payment"),
                data=json.dumps({
                    "purchase_id": compra.pk,
                    "form_data": {"transaction_amount": 120, "payment_method_id": "pix"},
                }),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["payment_id"], "pay_antigo")

    def test_dash_creator_continua_gerando_codigo(self):
        compra = _compra(product_key="dashcreator", product_name="Dash Creator", amount=Decimal("134.90"))
        _approve_purchase(compra, {"id": "pay_dash", "payment_method_id": "pix"})
        compra.refresh_from_db()
        self.assertIsNotNone(compra.access_code)
        self.assertIn(compra.access_code.code, mail.outbox[0].body)
